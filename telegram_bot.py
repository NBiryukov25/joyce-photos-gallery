#!/usr/bin/env python3
"""
Telegram bot: send a photo → uploads to GitHub → updates gallery HTML → site rebuilds.

Required env vars:
  TELEGRAM_BOT_TOKEN       — from @BotFather
  GITHUB_TOKEN             — GitHub personal access token (repo write access)

Optional env vars:
  TELEGRAM_ALLOWED_USER_ID — your Telegram user ID to restrict access
  GITHUB_REPO              — defaults to NBiryukov25/joyce-photos-gallery
  GITHUB_BRANCH            — defaults to main
"""

import asyncio
import base64
import io
import json
import os
import re
import logging
import shutil
import sys
import tempfile
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic as _anthropic_sdk
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    PicklePersistence,
    filters,
)

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set. Add it in Railway → Variables, then redeploy.")
    raise SystemExit(0)

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
# Extract just the token if someone accidentally pasted label text around it
_tok_match = re.search(r"(github_pat_\S+|ghp_\S+|ghs_\S+)", GITHUB_TOKEN)
if _tok_match:
    GITHUB_TOKEN = _tok_match.group(1)
else:
    GITHUB_TOKEN = GITHUB_TOKEN.strip()
GITHUB_REPO     = os.environ.get("GITHUB_REPO", "NBiryukov25/joyce-photos-gallery")
GITHUB_BRANCH   = os.environ.get("GITHUB_BRANCH", "main")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@filipina_allure")
ALLOWED_USER_ID   = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "")
TRANSCRIBE_API_TOKEN = os.environ.get("TRANSCRIBE_API_TOKEN", "")

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import chunk_audio as _chunk_audio

_repo_owner, _repo_name = GITHUB_REPO.split("/", 1)
GITHUB_PAGES_URL = f"https://{_repo_owner}.github.io/{_repo_name}"

CHOOSING_GALLERY, NAMING_GALLERY, CHOOSING_FRIEND_GALLERY, NAMING_FRIEND_GALLERY, ADDING_CAPTION, ADDING_MORE, REMOVING_GALLERY, REMOVING_FILE, CAPTION_GALLERY, CAPTION_FILE, CAPTION_TEXT, CHOOSING_ULTRA_GALLERY, NAMING_ULTRA_GALLERY, FEATURE_TITLE, FEATURE_PHOTOS, FEATURE_CAPTION, FCAP_CHOOSE, REORDER_GALLERY, REORDER_ORDER, SHARE_GALLERY, CHOOSING_SENZA_GALLERY, NAMING_SENZA_GALLERY, PHOTO_GALLERY, PHOTO_NUMBER, PHOTO_ACTION = range(25)

_SKIP_CB = "sc"  # callback_data for the inline Skip Caption button
_SKIP_KB = InlineKeyboardMarkup([[InlineKeyboardButton("Skip Caption →", callback_data=_SKIP_CB)]])

SPECIAL_HTML: dict[str, str] = {
    "Stashed-companion": "galleries/Stashed-companion.html",
}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

_GH_API = "https://api.github.com"
_GH_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# ---------------------------------------------------------------------------
# async GitHub API helpers
# ---------------------------------------------------------------------------


async def _gh_get_file(rel_path: str) -> tuple[bytes | None, str | None]:
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel_path}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_GH_HEADERS, params={"ref": GITHUB_BRANCH})
    if r.status_code == 200:
        data = r.json()
        return base64.b64decode(data["content"]), data["sha"]
    return None, None


async def _gh_put_file(rel_path: str, content: bytes, message: str, sha: str | None = None) -> tuple[bool, str]:
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN not set in Railway Variables"
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel_path}"
    body: dict = {
        "message": message,
        "content": base64.b64encode(content).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha
    timeout = httpx.Timeout(connect=15.0, write=120.0, read=60.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.put(url, json=body, headers=_GH_HEADERS)
        if r.status_code in (200, 201):
            return True, ""
        try:
            msg = r.json().get("message", f"HTTP {r.status_code}")
        except Exception:
            msg = f"HTTP {r.status_code}"
        return False, msg
    except httpx.TimeoutException as e:
        return False, f"Timed out contacting GitHub ({e.__class__.__name__})"
    except Exception as e:
        return False, f"Network error: {e}"


async def _gh_delete_file(rel_path: str, sha: str, message: str) -> tuple[bool, str]:
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN not set"
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel_path}"
    body = {"message": message, "sha": sha, "branch": GITHUB_BRANCH}
    timeout = httpx.Timeout(connect=10.0, write=30.0, read=30.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request("DELETE", url, json=body, headers=_GH_HEADERS)
        if r.status_code == 200:
            return True, ""
        try:
            msg = r.json().get("message", f"HTTP {r.status_code}")
        except Exception:
            msg = f"HTTP {r.status_code}"
        return False, msg
    except httpx.TimeoutException as e:
        return False, f"Timed out ({e.__class__.__name__})"
    except Exception as e:
        return False, f"Network error: {e}"


async def _list_gallery_files(gallery: str) -> list[dict]:
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/assets/{gallery}"
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=_GH_HEADERS, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return sorted(
                (item for item in r.json() if item["type"] == "file"),
                key=lambda x: x["name"],
                reverse=True,  # newest first (timestamp filenames)
            )
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# gallery helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"videos", "audio", "Gallery_photos", "Joyce-and-Friends", "Feature"}


async def _existing_galleries() -> list[str]:
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/assets"
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=_GH_HEADERS, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return sorted(
                item["name"] for item in r.json()
                if item["type"] == "dir"
                and not item["name"].startswith(".")
                and not item["name"].startswith("Feature-")
                and item["name"] not in _SKIP_DIRS
            )
    except Exception:
        pass
    return []


def _compress_photo(data: bytes, max_dimension: int = 1600, quality: int = 78) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_dimension:
        scale = max_dimension / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _make_filename(use_original: bool, original_name: str, is_video: bool = False, index: int = 0) -> str:
    if use_original:
        return original_name
    ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    idx = f"-{index:02d}" if index > 0 else ""
    return f"video-{ts}{idx}.mp4" if is_video else f"photo-{ts}{idx}.jpg"


_VIDEO_EXTS = frozenset({"mp4", "mov", "webm", "m4v", "avi"})


def _safe_js(value: str) -> str:
    return (value.replace("\\", "\\\\")
                 .replace("'", "\\'")
                 .replace("\r", "")
                 .replace("\n", " "))


def _safe_html(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _insert_into_js_array(text: str, var_name: str, value: str) -> str:
    pattern = rf"(var {re.escape(var_name)}\s*=\s*\[)([\s\S]*?)(\];)"

    def replacer(m: re.Match) -> str:
        pre, content, post = m.group(1), m.group(2), m.group(3)
        stripped = content.rstrip()
        if stripped and not stripped.endswith(","):
            stripped += ","
        return pre + stripped + f"\n        '{_safe_js(value)}',\n      " + post

    return re.sub(pattern, replacer, text)


def _get_js_array_entries(text: str, var_name: str) -> list[str]:
    m = re.search(rf"var {re.escape(var_name)}\s*=\s*\[([\s\S]*?)\];", text)
    if not m:
        return []
    return re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))


def _set_js_array(text: str, var_name: str, entries: list[str]) -> str:
    if entries:
        inner = "\n        " + "\n        ".join(f"'{e}'," for e in entries) + "\n      "
    else:
        inner = ""
    new_decl = f"var {var_name} = [{inner}];"
    return re.sub(rf"var {re.escape(var_name)}\s*=\s*\[[\s\S]*?\];", new_decl, text)


def _remove_from_gallery_html(current: bytes, gallery: str, filename: str) -> bytes:
    text = current.decode("utf-8")

    if re.search(r"var filenames\s*=\s*\[", text):
        filenames = _get_js_array_entries(text, "filenames")
        if filename in filenames:
            idx = filenames.index(filename)
            filenames.pop(idx)
            text = _set_js_array(text, "filenames", filenames)
            captions = _get_js_array_entries(text, "captions")
            if captions and idx < len(captions):
                captions.pop(idx)
                text = _set_js_array(text, "captions", captions)

    elif re.search(r'class="photo-grid"', text):
        # Try both path prefixes: galleries/ subdir uses ../, root-level uses plain
        for _prefix in (f"../assets/{gallery}/{filename}", f"assets/{gallery}/{filename}"):
            _src = f'src="{_prefix}"'
            _pos = text.find(_src)
            if _pos == -1:
                continue
            _open_tag = '<div class="photo-item">'
            _bs = text.rfind(_open_tag, 0, _pos)
            if _bs == -1:
                break
            # Walk forward tracking div nesting depth to find the matching </div>
            _i = _bs + len(_open_tag)
            _depth = 1
            while _depth > 0 and _i < len(text):
                _o = text.find('<div', _i)
                _c = text.find('</div>', _i)
                if _c == -1:
                    _depth = 0
                    break
                if _o != -1 and _o < _c:
                    _depth += 1
                    _i = _o + 4
                else:
                    _depth -= 1
                    _i = _c + 6
            _be = _i
            # Strip leading indent + preceding newline
            _trim = _bs
            while _trim > 0 and text[_trim - 1] in ' \t':
                _trim -= 1
            if _trim > 0 and text[_trim - 1] == '\n':
                _trim -= 1
            # Strip trailing newline
            if _be < len(text) and text[_be] == '\n':
                _be += 1
            text = text[:_trim] + text[_be:]
            break

    return text.encode("utf-8")


def _updated_html(current: bytes, gallery: str, filename: str, caption: str, html_rel: str = "") -> bytes:
    text = current.decode("utf-8")

    if re.search(r"var filenames\s*=\s*\[", text):
        # Slideshow gallery: update JS arrays
        text = _insert_into_js_array(text, "filenames", filename)
        if re.search(r"var captions\s*=\s*\[", text):
            text = _insert_into_js_array(text, "captions", caption)
    elif re.search(r'class="bento-gallery"', text):
        # Bento grid gallery: append a figure element
        asset_path = f"../assets/{gallery}/{filename}"
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in _VIDEO_EXTS:
            media_tag = f'        <video controls src="{asset_path}" style="width:100%;display:block;"></video>'
        else:
            media_tag = f'        <img src="{asset_path}" alt="{_safe_html(caption or "Photo")}">'
        new_item = (
            f'\n      <figure class="bento-item">\n'
            f'{media_tag}\n'
            f'        <figcaption>{_safe_html(caption)}</figcaption>\n'
            f'      </figure>'
        )
        text = re.sub(
            r'(\n\s+</div>\s*\n\s*</section>)',
            new_item + r'\1',
            text,
            count=1,
        )
    elif re.search(r'class="photo-grid"', text):
        # Photo-grid gallery — galleries in the galleries/ subdir need ../assets/ prefix
        in_subdir = html_rel.startswith("galleries/")
        asset_path = f"../assets/{gallery}/{filename}" if in_subdir else f"assets/{gallery}/{filename}"
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in _VIDEO_EXTS:
            media_tag = f'      <video controls src="{asset_path}" style="width:100%;display:block;border-radius:4px;"></video>'
        else:
            media_tag = f'      <img src="{asset_path}" alt="{_safe_html(caption or "Photo")}">'
        new_item = (
            f'    <div class="photo-item">\n'
            f'{media_tag}\n'
            f'      <div class="photo-info">\n'
            f'        <p class="photo-caption">{_safe_html(caption)}</p>\n'
            f'      </div>\n'
            f'    </div>'
        )
        # Insert before the photo-grid's closing </div> using rfind for reliability
        end_marker = '\n\n  </div>'
        pos = text.rfind(end_marker)
        if pos != -1:
            text = text[:pos] + '\n\n' + new_item + text[pos:]

    return text.encode("utf-8")


def _new_gallery_html(template: bytes, gallery: str, filename: str, caption: str) -> bytes:
    text = template.decode("utf-8")
    title = gallery.replace("-", " ").title()
    text = text.replace("GALLERY TITLE", title)
    text = text.replace("ASSET-FOLDER-NAME", gallery)
    text = re.sub(
        r"var filenames\s*=\s*\[[\s\S]*?\];",
        f"var filenames = [\n        '{_safe_js(filename)}'\n      ];",
        text,
    )
    if caption:
        # Match either array literal (var captions = [...];) or map() call (var captions = x.map(...});)
        text = re.sub(
            r"var captions\s*=[\s\S]*?(?:\]\s*;|\}\s*\)\s*;)",
            f"var captions = [\n        '{_safe_js(caption)}'\n      ];",
            text,
        )
    return text.encode("utf-8")


def _html_rel_path(gallery: str) -> str:
    return SPECIAL_HTML.get(gallery) or f"galleries/{gallery.lower()}.html"


def _update_gallery_index(gallery_html: bytes, gallery: str, filename: str) -> bytes:
    text = gallery_html.decode("utf-8")
    html_path = _html_rel_path(gallery)
    if html_path in text:
        return gallery_html  # already linked
    name = gallery.replace("-", " ").title()
    img_src = f"assets/{gallery}/{filename}"
    card = (
        f'<div class="gallery-item">'
        f'<a href="{html_path}"><img src="{img_src}" alt="{_safe_html(name)}"></a>'
        f'<div class="gallery-caption">'
        f'<p class="gallery-caption-title">{_safe_html(name)}</p>'
        f'<a class="gallery-view-link" href="{html_path}">View full series →</a>'
        f'</div></div>\n'
    )
    updated = text.replace('<!-- new-gallery-insert -->', card + '<!-- new-gallery-insert -->')
    # Show the section label once there's content
    updated = updated.replace(
        'id="new-galleries-label" style="display:none"',
        'id="new-galleries-label"',
    )
    return updated.encode("utf-8")


def _update_friends_index(friends_html: bytes, gallery: str, filename: str) -> bytes:
    text = friends_html.decode("utf-8")
    html_path = _html_rel_path(gallery)
    if html_path in text:
        return friends_html  # card already present
    name = gallery.replace("Friends-", "").replace("-", " ").title()
    img_src = f"assets/{gallery}/{filename}"
    card = (
        f'<div class="gallery-item">'
        f'<a href="{html_path}"><img src="{img_src}" alt="{_safe_html(name)}"></a>'
        f'<div class="gallery-caption">'
        f'<p class="gallery-caption-title">{_safe_html(name)}</p>'
        f'<a class="gallery-view-link" href="{html_path}">View gallery →</a>'
        f'</div></div>\n'
    )
    return text.replace('<!-- friend-gallery-insert -->', card + '<!-- friend-gallery-insert -->').encode("utf-8")


def _update_ultra_index(ultra_html: bytes, gallery: str, filename: str) -> bytes:
    text = ultra_html.decode("utf-8")
    html_path = _html_rel_path(gallery)
    if html_path in text:
        return ultra_html  # card already present
    name = gallery.replace("Ultra-", "").replace("-", " ").title()
    img_src = f"assets/{gallery}/{filename}"
    card = (
        f'<div class="gallery-item">'
        f'<a href="{html_path}"><img src="{img_src}" alt="{_safe_html(name)}"></a>'
        f'<div class="gallery-caption">'
        f'<p class="gallery-caption-title">{_safe_html(name)}</p>'
        f'<a class="gallery-view-link" href="{html_path}">View gallery →</a>'
        f'</div></div>\n'
    )
    return text.replace('<!-- ultra-gallery-insert -->', card + '<!-- ultra-gallery-insert -->').encode("utf-8")


def _update_senza_index(senza_html: bytes, gallery: str, filename: str) -> bytes:
    text = senza_html.decode("utf-8")
    html_path = _html_rel_path(gallery)
    if html_path in text:
        return senza_html  # card already present
    name = gallery.replace("-", " ").title()
    img_src = f"assets/{gallery}/{filename}"
    card = (
        f'    <div class="gallery-item">'
        f'<a href="{html_path}" data-collection="{gallery.lower()}">'
        f'<img loading="lazy" decoding="async" src="{img_src}" alt="{_safe_html(name)}"></a>'
        f'<div class="gallery-caption">'
        f'<p class="gallery-caption-title">{_safe_html(name)}</p>'
        f'<a class="gallery-view-link" href="{html_path}">View full series →</a>'
        f'</div></div>\n'
    )
    return text.replace('<!-- senza-gallery-insert -->', card + '<!-- senza-gallery-insert -->').encode("utf-8")


# ---------------------------------------------------------------------------
# Portrait API  (FastAPI served alongside the Telegram bot on $PORT)
# ---------------------------------------------------------------------------

portrait_api = FastAPI(title="Portrait API", docs_url=None, redoc_url=None)
portrait_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

_PORTRAIT_SYSTEM = """\
You are a literary portrait writer with a cinematic, intimate, sensory style. \
You excavate the hidden psychology of characters — what they show, what they believe, and what drives them.

Given a character description, write three short vivid portraits:

PERSONA — what they project to the world. Observational, exterior, third person.
EGO    — the story they tell themselves. Interior, self-justifying, their own mythology.
SHADOW — what drives them from beneath. Raw, elemental, the thing they cannot name even to themselves.

Style reference from existing work:

Persona: "Joyce stands at the water's edge, her petite frame outlined by the rushing current. \
The sunlight illuminates the golden undertones of her warm olive skin, a visual cue of a life \
that feels both familiar and suddenly urgent to explore. She holds herself with the careful \
stillness of someone who has learned to present only what she intends."

Ego: "Beneath the dappled light of the canopy, her expression is one of quiet determination. \
She gazes beyond the ancient forest surrounding her, embodying the restless energy of a woman \
seeking to redefine herself — not escaping, she tells herself, but finally arriving."

Shadow: "A velvet vice that tightens with every deliberate beat, holding him in a grip so fierce \
it feels almost like surrender. The searing pull of want beneath composed skin, radiating a heat \
that lingers long after she turns away."

Return ONLY valid JSON, nothing else:
{"persona": "...", "ego": "...", "shadow": "..."}

Each section: 2–4 sentences. Sensory. Specific. No clichés.\
"""


class _PortraitRequest(BaseModel):
    name:       str = ""
    bio:        str = ""
    appearance: str = ""
    drive:      str = ""
    desire:     str = ""
    secret:     str = ""
    fear:       str = ""
    arc:        str = ""
    voice:      str = ""
    # legacy single-field support
    description: str = ""


def _build_portrait_prompt(req: _PortraitRequest) -> str:
    parts = []
    if req.name:       parts.append(f"Name: {req.name}")
    if req.bio:        parts.append(f"Bio: {req.bio}")
    if req.appearance: parts.append(f"Appearance: {req.appearance}")
    if req.drive:      parts.append(f"Core Motivation (Drive): {req.drive}")
    if req.desire:     parts.append(f"Explicit Goal (Desire): {req.desire}")
    if req.secret:     parts.append(f"Hidden Secret: {req.secret}")
    if req.fear:       parts.append(f"Deepest Fear: {req.fear}")
    if req.arc:        parts.append(f"Character Arc: {req.arc}")
    if req.voice:      parts.append(f"Voice & Speech: {req.voice}")
    if not parts and req.description:
        parts.append(req.description)
    if not parts:
        raise HTTPException(status_code=400, detail="At least one field is required.")
    profile = "\n".join(parts)
    return (
        f"Write a three-part literary portrait for this character:\n\n{profile}\n\n"
        "Ground the PERSONA in their appearance, voice, and public behavior. "
        "Ground the EGO in their drive, desire, and arc. "
        "Ground the SHADOW in their secret, fear, and the gap between what they want and what drives them."
    )


_INFER_SYSTEM = """\
You are a perceptive character analyst. Given freeform observations about a person — real or imaginary — \
extract and infer structured character attributes. Read between the lines. \
Infer motivation from behavior, fear from avoidance, desire from what they pursue. \
Be specific and psychologically astute, not generic.

Return ONLY valid JSON with exactly these keys (use "" for anything truly unknowable):
{"name":"","bio":"","appearance":"","drive":"","desire":"","secret":"","fear":"","arc":"","voice":""}\
"""


class _InferRequest(BaseModel):
    observations: str


@portrait_api.post("/infer")
async def _infer_character(req: _InferRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Service not configured.")
    obs = req.observations.strip()
    if not obs:
        raise HTTPException(status_code=400, detail="Observations are required.")
    if len(obs) > 3000:
        raise HTTPException(status_code=400, detail="Observations too long (max 3000 characters).")
    try:
        client = _anthropic_sdk.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=_INFER_SYSTEM,
            messages=[{"role": "user", "content": f"Analyze these observations and infer character attributes:\n\n{obs}"}],
        )
        raw = message.content[0].text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise ValueError("Unexpected response format.")
        data = json.loads(m.group())
        keys = ['name', 'bio', 'appearance', 'drive', 'desire', 'secret', 'fear', 'arc', 'voice']
        return {k: data.get(k, "") for k in keys}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Infer failed")
        raise HTTPException(status_code=500, detail=str(exc))


@portrait_api.get("/health")
async def _health():
    return {"status": "ok"}


@portrait_api.post("/portrait")
async def _generate_portrait(req: _PortraitRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Portrait service not configured (ANTHROPIC_API_KEY missing).")
    try:
        user_prompt = _build_portrait_prompt(req)
        client = _anthropic_sdk.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=_PORTRAIT_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise ValueError("Unexpected response format from model.")
        data = json.loads(m.group())
        return {
            "persona": data.get("persona", ""),
            "ego":     data.get("ego", ""),
            "shadow":  data.get("shadow", ""),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Portrait generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Transcription API  (long .mp3/.mov -> verbatim .txt, chunked through
# Groq's Whisper API so hour-plus recordings stay under its 25 MB cap)
# ---------------------------------------------------------------------------

_TRANSCRIBE_JOBS: dict[str, dict] = {}
_TRANSCRIBE_TMP_ROOT = Path(tempfile.gettempdir()) / "joyce_transcribe_jobs"


def _check_transcribe_auth(authorization: str) -> None:
    if not TRANSCRIBE_API_TOKEN:
        raise HTTPException(status_code=503, detail="Transcription service not configured (TRANSCRIBE_API_TOKEN missing).")
    token = authorization.removeprefix("Bearer ").strip()
    if token != TRANSCRIBE_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token.")


async def _whisper_transcribe_chunk(client: httpx.AsyncClient, chunk_path: Path) -> str:
    audio_bytes = await asyncio.to_thread(chunk_path.read_bytes)
    resp = await client.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        data={"model": "whisper-large-v3", "response_format": "text"},
        files={"file": (chunk_path.name, audio_bytes, "audio/mpeg")},
    )
    resp.raise_for_status()
    return resp.text.strip()


def _chunk_job_file(media_path: Path, chunks_dir: Path) -> list[Path]:
    """Blocking ffmpeg work — run this inside asyncio.to_thread."""
    _chunk_audio.check_ffmpeg()
    chunks_dir.mkdir(parents=True, exist_ok=True)
    tmp_audio = chunks_dir.parent / "extracted_full.mp3"
    try:
        _chunk_audio.extract_audio(media_path, tmp_audio, "64k")
        duration = _chunk_audio.get_duration_seconds(tmp_audio)
        chunk_seconds = int((24_000_000 * 8 * 0.9) / _chunk_audio.parse_bitrate("64k"))
        return _chunk_audio.split_into_chunks(tmp_audio, chunks_dir, chunk_seconds)
    finally:
        tmp_audio.unlink(missing_ok=True)


async def _process_transcription_job(job_id: str, media_path: Path) -> None:
    job = _TRANSCRIBE_JOBS[job_id]
    job_dir = media_path.parent
    try:
        job["status"] = "chunking"
        chunks = await asyncio.to_thread(_chunk_job_file, media_path, job_dir / "chunks")
        if not chunks:
            raise RuntimeError("No audio chunks were produced.")

        job["status"] = "transcribing"
        job["total_chunks"] = len(chunks)
        transcript_parts = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            for i, chunk_path in enumerate(chunks, 1):
                job["progress"] = f"{i}/{len(chunks)}"
                text = await _whisper_transcribe_chunk(client, chunk_path)
                if text:
                    transcript_parts.append(text)

        job["status"] = "done"
        job["text"] = " ".join(transcript_parts)
    except Exception as exc:
        logger.exception("Transcription job %s failed", job_id)
        job["status"] = "error"
        job["error"] = str(exc)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@portrait_api.post("/transcribe/start")
async def _start_transcription(authorization: str = Header(default=""), file: UploadFile = File(...)):
    _check_transcribe_auth(authorization)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _chunk_audio.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}. Expected .mp3, .mov, or .mp4")

    job_id = uuid.uuid4().hex
    job_dir = _TRANSCRIBE_TMP_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    media_path = job_dir / f"source{suffix}"

    def _save():
        with media_path.open("wb") as out_f:
            shutil.copyfileobj(file.file, out_f)

    await asyncio.to_thread(_save)

    _TRANSCRIBE_JOBS[job_id] = {"status": "queued", "progress": "", "text": "", "error": ""}
    asyncio.create_task(_process_transcription_job(job_id, media_path))

    return {"job_id": job_id, "status": "queued"}


@portrait_api.get("/transcribe/status/{job_id}")
async def _transcription_status(job_id: str, authorization: str = Header(default="")):
    _check_transcribe_auth(authorization)
    job = _TRANSCRIBE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id.")
    return job


# ---------------------------------------------------------------------------
# authorization
# ---------------------------------------------------------------------------


def _authorized(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return str(update.effective_user.id) == ALLOWED_USER_ID


# ---------------------------------------------------------------------------
# command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Joyce Gallery Bot\n\n"
        "Send a photo or video to add it to a gallery.\n"
        "Send as a file to preserve full quality.\n\n"
        "/galleries — list existing galleries\n"
        "/remove    — delete a photo or video\n"
        "/reorder   — rearrange photo order in a gallery\n"
        "/share     — generate a standalone shareable gallery link\n"
        "/sync      — post all existing photos to the channel\n"
        "/done      — finish a batch upload\n"
        "/cancel    — cancel current operation"
    )


async def cmd_galleries(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    galleries = await _existing_galleries()
    if galleries:
        lines = "\n".join(f"• {g}" for g in galleries)
        await update.message.reply_text(f"Galleries:\n{lines}")
    else:
        await update.message.reply_text("No galleries found.")


async def _all_asset_dirs() -> list[str]:
    """All asset directories, including ones skipped from the upload menu."""
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/assets"
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=_GH_HEADERS, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return sorted(
                item["name"] for item in r.json()
                if item["type"] == "dir"
                and not item["name"].startswith(".")
                and item["name"] not in {"videos", "audio", "Gallery_photos"}
            )
    except Exception:
        pass
    return []


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    if not TELEGRAM_CHANNEL:
        await update.message.reply_text("TELEGRAM_CHANNEL is not set in Railway variables.")
        return

    status = await update.message.reply_text("Starting sync — fetching gallery list…")
    galleries = await _all_asset_dirs()
    if not galleries:
        await status.edit_text("No galleries found.")
        return

    sent = 0
    failed = 0

    for gallery in galleries:
        files = await _list_gallery_files(gallery)
        if not files:
            continue

        # Build caption map: filename → caption text
        html_rel = _html_rel_path(gallery)
        caption_map: dict[str, str] = {}
        gallery_html, _ = await _gh_get_file(html_rel)
        if gallery_html:
            text = gallery_html.decode("utf-8")
            fn_list  = _get_js_array_entries(text, "filenames")
            cap_list = _get_js_array_entries(text, "captions")
            for i, fn in enumerate(fn_list):
                caption_map[fn] = cap_list[i] if i < len(cap_list) else ""

        await status.edit_text(
            f"Syncing {gallery} ({len(files)} files)…\n"
            f"Sent so far: {sent}"
        )

        for file_info in reversed(files):  # oldest first
            filename = file_info["name"]
            ext = filename.rsplit(".", 1)[-1].lower()
            caption = caption_map.get(filename) or None

            try:
                timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.get(file_info["download_url"], headers=_GH_HEADERS)
                file_bytes = r.content
            except Exception as e:
                logger.warning("Sync: download failed %s: %s", filename, e)
                failed += 1
                continue

            try:
                if ext in _VIDEO_EXTS:
                    await context.bot.send_video(
                        chat_id=TELEGRAM_CHANNEL, video=file_bytes, caption=caption
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=TELEGRAM_CHANNEL, photo=file_bytes, caption=caption
                    )
                sent += 1
                await asyncio.sleep(1.5)  # stay well within Telegram rate limits
            except Exception as e:
                logger.warning("Sync: channel send failed %s: %s", filename, e)
                failed += 1

    await status.edit_text(
        f"✓ Sync complete.\n"
        f"Posted: {sent}  ·  Failed: {failed}"
    )


# ---------------------------------------------------------------------------
# conversation: photo → gallery → caption → done
# ---------------------------------------------------------------------------


_MAX_VIDEO_BYTES = 20 * 1024 * 1024  # Telegram Bot API hard limit


def _store_media(msg, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Populate context.user_data from a photo/video/document message.
    Returns an error string if the file is too large, else None."""
    ud = context.user_data
    if msg.video:
        size = msg.video.file_size or 0
        if size > _MAX_VIDEO_BYTES:
            return f"Video is too large ({size // (1024*1024)} MB). Max 20 MB."
        ud["file_id"] = msg.video.file_id
        ud["original_name"] = "video.mp4"
        ud["use_original"] = False
        ud["is_video"] = True
    elif msg.document:
        mime = msg.document.mime_type or ""
        is_vid = mime.startswith("video/")
        if is_vid:
            size = msg.document.file_size or 0
            if size > _MAX_VIDEO_BYTES:
                return f"Video is too large ({size // (1024*1024)} MB). Max 20 MB."
        ud["file_id"] = msg.document.file_id
        ud["original_name"] = msg.document.file_name or ("video.mp4" if is_vid else "photo.jpg")
        ud["use_original"] = True
        ud["is_video"] = is_vid
    else:
        ud["file_id"] = msg.photo[-1].file_id
        ud["original_name"] = "photo.jpg"
        ud["use_original"] = False
        ud["is_video"] = False
    return None


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END

    err = _store_media(update.message, context)
    if err:
        await update.message.reply_text(err)
        return ConversationHandler.END

    album_id = update.message.media_group_id
    if album_id:
        item = {k: context.user_data[k] for k in ("file_id", "original_name", "use_original", "is_video")}
        if context.user_data.get("pending_album_id") == album_id:
            # Same album still arriving — buffer silently, picker already shown
            context.user_data["pending_album"].append(item)
            return CHOOSING_GALLERY
        # First photo of a new album
        context.user_data["pending_album_id"] = album_id
        context.user_data["pending_album"] = [item]
    else:
        context.user_data.pop("pending_album_id", None)
        context.user_data.pop("pending_album", None)

    try:
        galleries = await _existing_galleries()
        regular = [g for g in galleries if not g.startswith("Friends-")]
        keyboard = [[InlineKeyboardButton(g, callback_data=f"g:{g}")] for g in regular]
        keyboard.append([
            InlineKeyboardButton("Galleries →", callback_data="g:__galleries__"),
            InlineKeyboardButton("Friends →", callback_data="g:__friends__"),
        ])
        keyboard.append([
            InlineKeyboardButton("Joyce Ultra →", callback_data="g:__ultra__"),
            InlineKeyboardButton("Senza Veli →", callback_data="g:__senza__"),
        ])
        await update.message.reply_text(
            "Which gallery?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CHOOSING_GALLERY
    except Exception as exc:
        logger.exception("Error in photo_received")
        await update.message.reply_text(f"Error starting upload: {exc}")
        return ConversationHandler.END


async def gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]

    if choice == "__new__":
        await query.edit_message_text("New gallery name? (e.g. Paris-Summer)")
        return NAMING_GALLERY

    if choice == "__galleries__":
        all_galleries = await _existing_galleries()
        main_galleries = [g for g in all_galleries if not g.startswith("Friends-") and not g.startswith("Ultra-")]
        keyboard = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"g:{g}")] for g in main_galleries]
        keyboard.append([InlineKeyboardButton("+ New Gallery", callback_data="g:__new__")])
        await query.edit_message_text("Which gallery? (added to gallery.html)", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_GALLERY

    if choice == "__friends__":
        all_galleries = await _existing_galleries()
        friend_galleries = [g for g in all_galleries if g.startswith("Friends-")]
        keyboard = [[InlineKeyboardButton(
            g.replace("Friends-", "").replace("-", " "),
            callback_data=f"f:{g}"
        )] for g in friend_galleries]
        keyboard.append([InlineKeyboardButton("+ New Friend Gallery", callback_data="f:__new__")])
        await query.edit_message_text("Which friend gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_FRIEND_GALLERY

    if choice == "__ultra__":
        all_galleries = await _existing_galleries()
        ultra_galleries = [g for g in all_galleries if g.startswith("Ultra-")]
        keyboard = [[InlineKeyboardButton(
            g.replace("Ultra-", "").replace("-", " "),
            callback_data=f"u:{g}"
        )] for g in ultra_galleries]
        keyboard.append([InlineKeyboardButton("+ New Ultra Gallery", callback_data="u:__new__")])
        await query.edit_message_text("Which Ultra gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_ULTRA_GALLERY

    if choice == "__senza__":
        all_galleries = await _existing_galleries()
        senza_galleries = [g for g in all_galleries if not g.startswith("Friends-") and not g.startswith("Ultra-")]
        keyboard = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"z:{g}")] for g in senza_galleries]
        keyboard.append([InlineKeyboardButton("+ New Senza Veli Gallery", callback_data="z:__new__")])
        await query.edit_message_text("Which Senza Veli gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_SENZA_GALLERY

    context.user_data["gallery"] = choice
    context.user_data["target_page"] = "gallery"
    n = len(context.user_data.get("pending_album") or [])
    count = f"{n} photos" if n > 1 else "photo"
    await query.edit_message_text(f"Adding {count} to {choice}.\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def friend_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]  # strips "f:"
    if choice == "__new__":
        await query.edit_message_text("Name this friend group (e.g. Nicole, Maria):")
        return NAMING_FRIEND_GALLERY
    context.user_data["gallery"] = choice
    context.user_data["target_page"] = "friends"
    name = choice.replace("Friends-", "").replace("-", " ").title()
    n = len(context.user_data.get("pending_album") or [])
    count = f"{n} photos" if n > 1 else "photo"
    await query.edit_message_text(f"Adding {count} to {name}.\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def friend_gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "Friend"
    gallery = f"Friends-{name}"
    context.user_data["gallery"] = gallery
    context.user_data["target_page"] = "friends"
    await update.message.reply_text(f"New friend gallery: {name.replace('-', ' ')}\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def ultra_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]  # strips "u:"
    if choice == "__new__":
        await query.edit_message_text("Name this Ultra gallery (e.g. Night-Session):")
        return NAMING_ULTRA_GALLERY
    context.user_data["gallery"] = choice
    context.user_data["target_page"] = "ultra"
    name = choice.replace("Ultra-", "").replace("-", " ").title()
    n = len(context.user_data.get("pending_album") or [])
    count = f"{n} photos" if n > 1 else "photo"
    await query.edit_message_text(f"Adding {count} to {name}.\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def ultra_gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "Ultra"
    gallery = f"Ultra-{name}"
    context.user_data["gallery"] = gallery
    context.user_data["target_page"] = "ultra"
    await update.message.reply_text(f"New Ultra gallery: {name.replace('-', ' ')}\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def senza_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]  # strips "z:"
    if choice == "__new__":
        await query.edit_message_text("Name this Senza Veli gallery (e.g. Night-Moves):")
        return NAMING_SENZA_GALLERY
    context.user_data["gallery"] = choice
    context.user_data["target_page"] = "senza"
    name = choice.replace("-", " ").title()
    n = len(context.user_data.get("pending_album") or [])
    count = f"{n} photos" if n > 1 else "photo"
    await query.edit_message_text(f"Adding {count} to {name} (Senza Veli).\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def senza_gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "New-Gallery"
    context.user_data["gallery"] = name
    context.user_data["target_page"] = "senza"
    await update.message.reply_text(f"New Senza Veli gallery: {name.replace('-', ' ')}\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "New-Gallery"
    context.user_data["gallery"] = name
    context.user_data["target_page"] = "gallery"
    await update.message.reply_text(f"Gallery: {name}\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = update.message.text.strip()
    return await _finalize(update, context)


async def caption_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = ""
    return await _finalize(update, context)


async def skip_caption_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    context.user_data["caption"] = ""
    return await _finalize(update, context)


async def more_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    err = _store_media(update.message, context)
    if err:
        await update.message.reply_text(err)
        return ConversationHandler.END

    album_id = update.message.media_group_id
    if album_id:
        item = {k: context.user_data[k] for k in ("file_id", "original_name", "use_original", "is_video")}
        if context.user_data.get("pending_album_id") == album_id:
            context.user_data["pending_album"].append(item)
            return ADDING_CAPTION  # prompt already shown
        context.user_data["pending_album_id"] = album_id
        context.user_data["pending_album"] = [item]
    else:
        context.user_data.pop("pending_album_id", None)
        context.user_data.pop("pending_album", None)

    gallery = context.user_data.get("gallery", "")
    display = gallery.replace("Friends-", "").replace("-", " ") if gallery.startswith("Friends-") else gallery
    n = len(context.user_data.get("pending_album") or [])
    count = f"{n} photos" if n > 1 else "photo"
    await update.message.reply_text(f"Adding {count} to {display}.\n\nCaption? (or tap Skip)", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def cmd_done(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Done. Send a photo any time to start a new upload.")
    return ConversationHandler.END


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        return await _finalize_inner(update, context)
    except Exception as exc:
        logger.exception("Unhandled error in _finalize")
        try:
            await update.effective_message.reply_text(
                f"Something went wrong: {exc}\n\nSend another photo to continue, or /done to finish."
            )
        except Exception:
            pass
        return ADDING_MORE


async def _upload_and_register(
    context,
    gallery: str,
    html_rel: str,
    item: dict,
    caption: str,
    index: int,
    current_html: bytes | None,
    html_sha: str | None,
) -> tuple[str, bytes, bytes, str | None]:
    """Download, compress, upload one photo/video. Returns (filename, upload_bytes, new_html, new_sha)."""
    file_id   = item["file_id"]
    use_orig  = item["use_original"]
    orig_name = item["original_name"]
    is_video  = item["is_video"]

    suffix = ".mp4" if is_video else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    tg_file = await context.bot.get_file(file_id)
    await asyncio.wait_for(tg_file.download_to_drive(str(tmp_path)), timeout=60)
    raw_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    upload_bytes = raw_bytes if is_video else _compress_photo(raw_bytes)
    filename = _make_filename(use_orig, orig_name, is_video=is_video, index=index)
    photo_rel = f"assets/{gallery}/{filename}"

    ok, err = await _gh_put_file(photo_rel, upload_bytes, f"Add {filename} to {gallery}")
    if not ok:
        raise RuntimeError(f"Upload failed for {filename}: {err}")

    if current_html is not None:
        new_html = _updated_html(current_html, gallery, filename, caption, html_rel=html_rel)
    else:
        template, _ = await _gh_get_file("galleries/_template-gallery.html")
        if not template:
            raise RuntimeError("Could not find gallery template.")
        new_html = _new_gallery_html(template, gallery, filename, caption)

    ok, err = await _gh_put_file(html_rel, new_html, f"Update {gallery} — add {filename}", sha=html_sha)
    if not ok:
        raise RuntimeError(f"Page update failed for {filename}: {err}")

    # Re-fetch sha for the next sequential write
    _, new_sha = await _gh_get_file(html_rel)
    return filename, upload_bytes, new_html, new_sha


async def _finalize_inner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gallery = context.user_data["gallery"]
    caption = context.user_data.get("caption", "")

    # Collect items — album batch or single photo
    pending = context.user_data.pop("pending_album", None)
    context.user_data.pop("pending_album_id", None)
    if pending and len(pending) > 0:
        items = pending
    else:
        items = [{
            "file_id":       context.user_data["file_id"],
            "original_name": context.user_data.get("original_name", "photo.jpg"),
            "use_original":  context.user_data.get("use_original", False),
            "is_video":      context.user_data.get("is_video", False),
        }]

    total = len(items)
    status = await update.effective_message.reply_text(
        f"Uploading 1 / {total}…" if total > 1 else "Downloading photo…"
    )

    html_rel = _html_rel_path(gallery)
    current_html, html_sha = await _gh_get_file(html_rel)
    first_html_sha = html_sha  # used to detect new gallery
    is_new_gallery = html_sha is None

    uploaded_files: list[tuple[str, bytes, bool]] = []  # (filename, bytes, is_video)
    failed = 0

    for i, item in enumerate(items):
        if total > 1:
            try:
                await status.edit_text(f"Uploading {i + 1} / {total}…")
            except Exception:
                pass
        try:
            filename, upload_bytes, current_html, html_sha = await _upload_and_register(
                context, gallery, html_rel, item, caption, i, current_html, html_sha
            )
            uploaded_files.append((filename, upload_bytes, item["is_video"]))
        except Exception as exc:
            logger.exception("Upload failed for item %d", i)
            failed += 1
            try:
                await status.edit_text(f"Photo {i + 1} failed: {exc}\nContinuing…")
            except Exception:
                pass

    if not uploaded_files:
        await status.edit_text("All uploads failed. Please try again.")
        return ConversationHandler.END

    # New gallery → add card to the appropriate index page
    if is_new_gallery:
        first_filename = uploaded_files[0][0]
        target_page = context.user_data.get("target_page", "")
        if gallery.startswith("Friends-"):
            friends_html, friends_sha = await _gh_get_file("friends.html")
            if friends_html:
                updated = _update_friends_index(friends_html, gallery, first_filename)
                if updated != friends_html:
                    await _gh_put_file("friends.html", updated, f"Add {gallery} to friends page", sha=friends_sha)
        elif gallery.startswith("Ultra-"):
            ultra_html, ultra_sha = await _gh_get_file("joyce-ultra.html")
            if ultra_html:
                updated = _update_ultra_index(ultra_html, gallery, first_filename)
                if updated != ultra_html:
                    await _gh_put_file("joyce-ultra.html", updated, f"Add {gallery} to Joyce Ultra", sha=ultra_sha)
        elif target_page == "senza":
            senza_html, senza_sha = await _gh_get_file("senza-veli.html")
            if senza_html:
                updated = _update_senza_index(senza_html, gallery, first_filename)
                if updated != senza_html:
                    await _gh_put_file("senza-veli.html", updated, f"Add {gallery} to Senza Veli", sha=senza_sha)
        else:
            gallery_html, gallery_sha = await _gh_get_file("gallery.html")
            if gallery_html:
                updated = _update_gallery_index(gallery_html, gallery, first_filename)
                if updated != gallery_html:
                    await _gh_put_file("gallery.html", updated, f"Add {gallery} to gallery index", sha=gallery_sha)

    gallery_url = f"{GITHUB_PAGES_URL}/{html_rel}"
    if gallery.startswith("Friends-"):
        display = gallery.replace("Friends-", "").replace("-", " ")
    elif gallery.startswith("Ultra-"):
        display = gallery.replace("Ultra-", "").replace("-", " ")
    else:
        display = gallery

    # Post to Telegram channel
    channel_note = ""
    if TELEGRAM_CHANNEL:
        chan_caption = caption if caption else None
        posted = 0
        for filename, upload_bytes, is_video in uploaded_files:
            try:
                if is_video:
                    await context.bot.send_video(chat_id=TELEGRAM_CHANNEL, video=upload_bytes, caption=chan_caption)
                else:
                    await context.bot.send_photo(chat_id=TELEGRAM_CHANNEL, photo=upload_bytes, caption=chan_caption)
                posted += 1
                chan_caption = None  # caption only on first
            except Exception as e:
                logger.warning("Channel post failed: %s", e)
        if posted:
            channel_note = f"\nPosted {posted} to {TELEGRAM_CHANNEL} ✓"

    ok_count = len(uploaded_files)
    summary = f"✓ {ok_count} photo{'s' if ok_count != 1 else ''} added to {display}."
    if failed:
        summary += f" ({failed} failed)"
    await status.edit_text(
        f"{summary}{channel_note}\n\n"
        f"Gallery: {gallery_url}\n\n"
        f"Send another photo for {display}, or /done to finish."
    )

    return ADDING_MORE


# ---------------------------------------------------------------------------
# /feature — Featured page (slideshow + caption → Joyce Ultra)
# ---------------------------------------------------------------------------


def _build_feature_html(title: str, folder: str, filenames: list[str], caption: str) -> bytes:
    safe_title = _safe_html(title)
    slides = []
    for i, fn in enumerate(filenames):
        active = " active" if i == 0 else ""
        ext = fn.rsplit(".", 1)[-1].lower()
        src = f"../assets/{folder}/{fn}"
        if ext in _VIDEO_EXTS:
            media = f'      <video src="{src}" muted loop autoplay playsinline style="width:100%;height:100%;object-fit:cover;display:block;"></video>'
        else:
            media = f'      <img src="{src}" alt="{safe_title}">'
        slides.append(f'    <div class="fp-slide{active}">\n{media}\n    </div>')
    slides_html = "\n\n".join(slides)

    paras = [p.strip() for p in caption.strip().split("\n\n") if p.strip()]
    if not paras and caption.strip():
        paras = [caption.strip()]
    cap_html = "\n".join(f"    <p>{_safe_html(p)}</p>" for p in paras)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title} · Joyce Ultra</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ min-height: 100%; background: #0c0a08; color: rgba(255,255,255,0.88); font-family: 'Cormorant Garamond', serif; }}
    .back-link {{ display: inline-block; font-family: 'Jost', sans-serif; font-size: 0.72rem; font-weight: 300; letter-spacing: 0.18em; color: rgba(201,169,110,0.7); text-decoration: none; padding: 1.2rem 1.5rem; }}
    .back-link:hover {{ color: #c9a96e; }}
    .fp-stage {{ position: relative; width: 100%; max-width: 860px; margin: 0 auto; aspect-ratio: 4/5; overflow: hidden; background: #060404; }}
    .fp-slide {{ position: absolute; inset: 0; opacity: 0; transition: opacity 0.9s ease; }}
    .fp-slide.active {{ opacity: 1; }}
    .fp-slide img, .fp-slide video {{ width: 100%; height: 100%; object-fit: cover; display: block; transform: scale(1); transition: transform 0s; }}
    .fp-slide.active img, .fp-slide.active video {{ transform: scale(1.06); transition: transform 9s ease-out; }}
    .fp-progress {{ height: 2px; background: rgba(255,255,255,0.08); max-width: 860px; margin: 0 auto; }}
    .fp-bar {{ height: 100%; width: 0%; background: #c9a96e; }}
    .fp-dots {{ display: flex; justify-content: center; gap: 0.5rem; padding: 0.9rem 0 0; }}
    .fp-dot {{ width: 5px; height: 5px; border-radius: 50%; background: rgba(255,255,255,0.2); border: none; cursor: pointer; padding: 0; transition: background 0.25s; }}
    .fp-dot.active {{ background: #c9a96e; }}
    .fp-header {{ max-width: 680px; margin: 2.4rem auto 0; padding: 0 1.5rem; text-align: center; }}
    .fp-title {{ font-family: 'Cormorant Garamond', serif; font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 400; letter-spacing: 0.06em; color: rgba(255,255,255,0.92); line-height: 1.2; }}
    .fp-rule {{ border: none; border-top: 1px solid rgba(201,169,110,0.28); margin: 1.2rem 0 0; }}
    .fp-caption {{ max-width: 680px; margin: 2rem auto 5rem; padding: 0 1.5rem; }}
    .fp-caption p {{ font-family: 'Cormorant Garamond', serif; font-size: 1.15rem; font-weight: 300; line-height: 1.85; color: rgba(255,255,255,0.7); }}
    .fp-caption p + p {{ margin-top: 1.2em; }}
    .fp-caption strong {{ color: rgba(255,255,255,0.9); font-weight: 500; }}
    .fp-caption em {{ font-style: italic; }}
    @media (max-width: 600px) {{ .fp-stage {{ aspect-ratio: 3/4; }} }}
  </style>
</head>
<body>

  <a class="back-link" href="../joyce-ultra.html">← Ultra</a>

  <div class="fp-stage" id="fp-stage" data-interval="8000">

{slides_html}

  </div>

  <div class="fp-progress"><div class="fp-bar" id="fp-bar"></div></div>
  <div class="fp-dots" id="fp-dots"></div>

  <div class="fp-header">
    <h1 class="fp-title">{safe_title}</h1>
    <hr class="fp-rule">
  </div>

  <div class="fp-caption">
{cap_html}
  </div>

  <script>
    (function () {{
      var stage    = document.getElementById('fp-stage');
      var barEl    = document.getElementById('fp-bar');
      var dotsWrap = document.getElementById('fp-dots');
      var slides   = Array.prototype.slice.call(stage.querySelectorAll('.fp-slide'));
      var N        = slides.length;
      var INTERVAL = parseInt(stage.getAttribute('data-interval'), 10) || 8000;
      var cur = 0, timer = null;
      if (N === 0) return;
      slides.forEach(function (_, i) {{
        var b = document.createElement('button');
        b.className = 'fp-dot' + (i === 0 ? ' active' : '');
        b.setAttribute('aria-label', 'Slide ' + (i + 1));
        b.addEventListener('click', function () {{ stop(); show(i); start(); }});
        dotsWrap.appendChild(b);
      }});
      var dots = dotsWrap.querySelectorAll('.fp-dot');
      function resetBar() {{
        barEl.style.transition = 'none'; barEl.style.width = '0%';
        requestAnimationFrame(function () {{ requestAnimationFrame(function () {{
          barEl.style.transition = 'width ' + INTERVAL + 'ms linear'; barEl.style.width = '100%';
        }}); }});
      }}
      function show(n) {{
        slides[cur].classList.remove('active'); if (dots[cur]) dots[cur].classList.remove('active');
        cur = (n + N) % N;
        slides[cur].classList.add('active');   if (dots[cur]) dots[cur].classList.add('active');
        resetBar();
      }}
      function start() {{ if (!timer && N > 1) timer = setInterval(function () {{ show(cur + 1); }}, INTERVAL); }}
      function stop()  {{ clearInterval(timer); timer = null; }}
      document.addEventListener('keydown', function (e) {{
        if (e.key === 'ArrowRight') {{ stop(); show(cur + 1); start(); }}
        if (e.key === 'ArrowLeft')  {{ stop(); show(cur - 1); start(); }}
      }});
      show(0); start();
    }})();
  </script>

</body>
</html>
"""
    return html.encode("utf-8")


def _update_ultra_featured(ultra_html: bytes, title: str, html_rel: str) -> bytes:
    text = ultra_html.decode("utf-8")
    if html_rel in text:
        return ultra_html
    card = (
        f'\n    <a class="ultra-story-card" href="{html_rel}">\n'
        f'      <p class="ultra-story-tag">Featured · Ultra</p>\n'
        f'      <h2 class="ultra-story-title">{_safe_html(title)}</h2>\n'
        f'      <span class="ultra-story-read">View →</span>\n'
        f'    </a>'
    )
    updated = text.replace("<!-- ultra-story-insert -->", card + "\n\n    <!-- ultra-story-insert -->")
    return updated.encode("utf-8")


async def cmd_feature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "Creating a Featured page for Joyce Ultra.\n\n"
        "What's the title for this piece?"
    )
    return FEATURE_TITLE


async def feature_title_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    slug = re.sub(r"[^\w\-]", "-", title.lower()).strip("-") or "feature"
    slug = re.sub(r"-+", "-", slug)
    context.user_data["feat_title"] = title
    context.user_data["feat_slug"] = slug
    context.user_data["feat_photos"] = []
    await update.message.reply_text(
        f'Title: "{title}"\n\n'
        f"Now send your photos one at a time.\n"
        f"/done when you've added all of them."
    )
    return FEATURE_PHOTOS


async def _upload_one_feature_photo(
    bot, folder: str, item: dict, index: int
) -> tuple[str | None, str | None]:
    """Download one photo/video from Telegram and upload to GitHub.
    Returns (filename, None) on success or (None, error_str) on failure."""
    file_id = item["file_id"]
    is_video = item["is_video"]
    use_orig = item["use_original"]
    orig_name = item["original_name"]

    try:
        suffix = ".mp4" if is_video else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        tg_file = await bot.get_file(file_id)
        await asyncio.wait_for(tg_file.download_to_drive(str(tmp_path)), timeout=120)
        raw_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        return None, f"Download failed: {exc}"

    try:
        upload_bytes = raw_bytes if is_video else _compress_photo(raw_bytes)
        filename = _make_filename(use_orig, orig_name, is_video=is_video, index=index)
        ok, err = await _gh_put_file(
            f"assets/{folder}/{filename}", upload_bytes, f"Add {filename} to {folder}"
        )
        if not ok:
            return None, err
        return filename, None
    except Exception as exc:
        return None, str(exc)


async def feature_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message

    slug = context.user_data.get("feat_slug")
    if not slug:
        await msg.reply_text("Session lost — please start over with /feature.")
        return ConversationHandler.END

    err = _store_media(msg, context)
    if err:
        await msg.reply_text(err)
        return FEATURE_PHOTOS

    folder = f"Feature-{slug}"
    is_video = context.user_data.get("is_video", False)
    kind = "video" if is_video else "photo"
    index = len(context.user_data.get("feat_photos", []))
    album_id = msg.media_group_id

    # For album photos reuse the same status message to keep chat tidy
    status_id   = context.user_data.get("feat_status_id")
    status_chat = context.user_data.get("feat_status_chat")
    last_album  = context.user_data.get("feat_last_album")

    if album_id and album_id == last_album and status_id and status_chat == msg.chat_id:
        try:
            await context.bot.edit_message_text(
                f"Uploading {kind} {index + 1}...",
                chat_id=status_chat, message_id=status_id
            )
        except Exception:
            st = await msg.reply_text(f"Uploading {kind} {index + 1}...")
            context.user_data["feat_status_id"]   = st.message_id
            context.user_data["feat_status_chat"]  = msg.chat_id
            status_id   = st.message_id
            status_chat = msg.chat_id
    else:
        st = await msg.reply_text(f"Uploading {kind} {index + 1}...")
        context.user_data["feat_status_id"]   = st.message_id
        context.user_data["feat_status_chat"]  = msg.chat_id
        context.user_data["feat_last_album"]   = album_id
        status_id   = st.message_id
        status_chat = msg.chat_id

    item = {
        "file_id":       context.user_data["file_id"],
        "is_video":      is_video,
        "use_original":  context.user_data.get("use_original", False),
        "original_name": context.user_data.get("original_name", "photo.jpg"),
    }
    filename, err = await _upload_one_feature_photo(context.bot, folder, item, index)
    if err:
        try:
            await context.bot.edit_message_text(
                f"Upload failed: {err}\n\nTry sending that photo again.",
                chat_id=status_chat, message_id=status_id
            )
        except Exception:
            await msg.reply_text(f"Upload failed: {err}\n\nTry sending that photo again.")
        return FEATURE_PHOTOS

    photos = context.user_data.setdefault("feat_photos", [])
    photos.append(filename)
    total = len(photos)
    try:
        await context.bot.edit_message_text(
            f"✓ {total} photo{'s' if total != 1 else ''} saved. Send more or /done.",
            chat_id=status_chat, message_id=status_id
        )
    except Exception:
        pass
    return FEATURE_PHOTOS


async def feature_ask_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photos = context.user_data.get("feat_photos", [])
    if not photos:
        await update.message.reply_text("No photos yet — send at least one photo first.")
        return FEATURE_PHOTOS
    n = len(photos)
    context.user_data["feat_caption_parts"] = []
    context.user_data.pop("feat_cap_status_id", None)
    st = await update.message.reply_text(
        f"{n} photo{'s' if n != 1 else ''} ready.\n\n"
        f"Type your story — each message is a paragraph. /done when finished.\n\n"
        f"Paragraphs: 0"
    )
    context.user_data["feat_cap_status_id"]   = st.message_id
    context.user_data["feat_cap_status_chat"]  = update.message.chat_id
    return FEATURE_CAPTION


async def feature_caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chunk = update.message.text.strip()
    if chunk:
        context.user_data.setdefault("feat_caption_parts", []).append(chunk)
    parts = context.user_data.get("feat_caption_parts", [])
    n = len(parts)

    # Edit the single status message instead of sending a new one every time,
    # so we never hit Telegram's outgoing message rate limit.
    status_id   = context.user_data.get("feat_cap_status_id")
    status_chat = context.user_data.get("feat_cap_status_chat")
    status_text = (
        f"Type your story — each message is a paragraph. /done when finished.\n\n"
        f"Paragraphs: {n}"
    )
    if status_id and status_chat == update.message.chat_id:
        try:
            await context.bot.edit_message_text(status_text, chat_id=status_chat, message_id=status_id)
        except Exception:
            st = await update.message.reply_text(status_text)
            context.user_data["feat_cap_status_id"]  = st.message_id
            context.user_data["feat_cap_status_chat"] = update.message.chat_id
    else:
        st = await update.message.reply_text(status_text)
        context.user_data["feat_cap_status_id"]  = st.message_id
        context.user_data["feat_cap_status_chat"] = update.message.chat_id
    return FEATURE_CAPTION


async def feature_caption_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # If we entered via /fcaption, delegate to the caption-only update handler
    if context.user_data.get("fcap_slug"):
        return await fcap_done(update, context)

    parts = context.user_data.get("feat_caption_parts", [])
    if not parts:
        await update.message.reply_text("No caption yet — type at least one paragraph, then /done.")
        return FEATURE_CAPTION

    caption = "\n\n".join(parts)
    slug  = context.user_data.get("feat_slug") or "the-employer-s-playground"
    title = context.user_data.get("feat_title") or slug.replace("-", " ").title()
    folder = f"Feature-{slug}"

    # Recover photo list from GitHub if session was restarted mid-flow
    photos = context.user_data.get("feat_photos") or []
    if not photos:
        gh_files = await _list_gallery_files(folder)
        photos = sorted(f["name"] for f in gh_files)

    # Reuse the caption status message if possible, otherwise send a new one
    status_id   = context.user_data.get("feat_cap_status_id")
    status_chat = context.user_data.get("feat_cap_status_chat")
    if status_id and status_chat == update.message.chat_id:
        try:
            await context.bot.edit_message_text(
                "Building featured page...", chat_id=status_chat, message_id=status_id
            )
            status = None
        except Exception:
            status = await update.message.reply_text("Building featured page...")
    else:
        status = await update.message.reply_text("Building featured page...")

    async def _edit_status(text: str) -> None:
        if status:
            await status.edit_text(text)
        else:
            try:
                await context.bot.edit_message_text(text, chat_id=status_chat, message_id=status_id)
            except Exception:
                await update.message.reply_text(text)

    try:
        html_bytes = _build_feature_html(title, folder, photos, caption)
    except Exception as exc:
        await _edit_status(f"Failed to build page: {exc}")
        return ConversationHandler.END

    html_rel = f"galleries/feature-{slug}.html"
    _, html_sha = await _gh_get_file(html_rel)

    ok, err = await _gh_put_file(html_rel, html_bytes, f"Add featured page: {title}", sha=html_sha)
    if not ok:
        await _edit_status(f"Page creation failed: {err}")
        return ConversationHandler.END

    ultra_ok = False
    for _attempt in range(2):
        ultra_html, ultra_sha = await _gh_get_file("joyce-ultra.html")
        if not ultra_html:
            break
        updated_ultra = _update_ultra_featured(ultra_html, title, html_rel)
        if updated_ultra == ultra_html:
            ultra_ok = True  # card already present
            break
        ok2, _err2 = await _gh_put_file(
            "joyce-ultra.html", updated_ultra,
            f"Add featured card: {title}", sha=ultra_sha
        )
        if ok2:
            ultra_ok = True
            break
        # SHA conflict on first attempt — re-fetch and retry once

    gallery_url = f"{GITHUB_PAGES_URL}/{html_rel}"
    ultra_line = "Card added to Joyce Ultra." if ultra_ok else "⚠️ Joyce Ultra card update failed — please add it manually."
    await _edit_status(
        f'✓ Featured page published!\n\n'
        f'"{title}" · {len(photos)} photo{"s" if len(photos) != 1 else ""} · {len(parts)} paragraph{"s" if len(parts) != 1 else ""}\n\n'
        f'{gallery_url}\n\n'
        f'{ultra_line}'
    )
    return ConversationHandler.END


def _replace_feature_caption(html_bytes: bytes, new_caption: str) -> bytes:
    text = html_bytes.decode("utf-8")
    paras = [p.strip() for p in new_caption.strip().split("\n\n") if p.strip()]
    if not paras:
        paras = [new_caption.strip()]
    cap_html = "\n".join(f"    <p>{_safe_html(p)}</p>" for p in paras)
    # Replace everything between <div class="fp-caption"> and the closing </div>
    updated = re.sub(
        r'(<div class="fp-caption">).*?(</div>)',
        lambda m: m.group(1) + "\n" + cap_html + "\n  " + m.group(2),
        text, count=1, flags=re.DOTALL
    )
    return updated.encode("utf-8")


async def _list_feature_pages() -> list[tuple[str, str]]:
    """Return list of (slug, html_rel) for existing feature pages."""
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/galleries"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=_GH_HEADERS, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return [
                (item["name"][len("feature-"):-5], item["path"])
                for item in r.json()
                if item["type"] == "file" and item["name"].startswith("feature-") and item["name"].endswith(".html")
            ]
    except Exception:
        pass
    return []


async def cmd_fcaption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    pages = await _list_feature_pages()
    if not pages:
        await update.message.reply_text("No featured pages found.")
        return ConversationHandler.END
    if len(pages) == 1:
        slug, html_rel = pages[0]
        context.user_data["fcap_slug"]    = slug
        context.user_data["fcap_rel"]     = html_rel
        context.user_data["feat_caption_parts"] = []
        context.user_data.pop("feat_cap_status_id", None)
        st = await update.message.reply_text(
            f"Editing caption for: {slug}\n\n"
            f"Type your story — each message is a paragraph. /done when finished.\n\n"
            f"Paragraphs: 0"
        )
        context.user_data["feat_cap_status_id"]  = st.message_id
        context.user_data["feat_cap_status_chat"] = update.message.chat_id
        return FEATURE_CAPTION
    context.user_data["fcap_pages"] = pages
    keyboard = [[InlineKeyboardButton(slug, callback_data=f"fc:{i}")] for i, (slug, _) in enumerate(pages)]
    await update.message.reply_text("Which featured page?", reply_markup=InlineKeyboardMarkup(keyboard))
    return FCAP_CHOOSE


async def fcap_page_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    slug, html_rel = context.user_data["fcap_pages"][idx]
    context.user_data["fcap_slug"]  = slug
    context.user_data["fcap_rel"]   = html_rel
    context.user_data["feat_caption_parts"] = []
    context.user_data.pop("feat_cap_status_id", None)
    st = await query.edit_message_text(
        f"Editing caption for: {slug}\n\n"
        f"Type your story — each message is a paragraph. /done when finished.\n\n"
        f"Paragraphs: 0"
    )
    context.user_data["feat_cap_status_id"]  = st.message_id
    context.user_data["feat_cap_status_chat"] = query.message.chat_id
    return FEATURE_CAPTION


async def fcap_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parts = context.user_data.get("feat_caption_parts", [])
    if not parts:
        await update.message.reply_text("No caption yet — type at least one paragraph, then /done.")
        return FEATURE_CAPTION

    slug    = context.user_data.get("fcap_slug", "")
    html_rel = context.user_data.get("fcap_rel", f"galleries/feature-{slug}.html")
    caption = "\n\n".join(parts)

    status_id   = context.user_data.get("feat_cap_status_id")
    status_chat = context.user_data.get("feat_cap_status_chat")

    async def _edit(text: str) -> None:
        if status_id and status_chat == update.message.chat_id:
            try:
                await context.bot.edit_message_text(text, chat_id=status_chat, message_id=status_id)
                return
            except Exception:
                pass
        await update.message.reply_text(text)

    await _edit("Updating caption...")

    existing, sha = await _gh_get_file(html_rel)
    if not existing:
        await _edit(f"Could not fetch {html_rel} from GitHub.")
        return ConversationHandler.END

    updated = _replace_feature_caption(existing, caption)
    ok, err = await _gh_put_file(html_rel, updated, f"Update caption: {slug}", sha=sha)
    if not ok:
        await _edit(f"Failed to save: {err}")
        return ConversationHandler.END

    gallery_url = f"{GITHUB_PAGES_URL}/{html_rel}"
    await _edit(
        f'✓ Caption updated!\n\n'
        f'{len(parts)} paragraph{"s" if len(parts) != 1 else ""}\n\n'
        f'{gallery_url}'
    )
    return ConversationHandler.END


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    galleries = await _existing_galleries()
    if not galleries:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    context.user_data["remove_galleries"] = galleries
    keyboard = [[InlineKeyboardButton(g, callback_data=f"rg:{i}")] for i, g in enumerate(galleries)]
    await update.message.reply_text("Remove from which gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
    return REMOVING_GALLERY


async def remove_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    gallery = context.user_data["remove_galleries"][idx]
    context.user_data["remove_gallery"] = gallery

    await query.edit_message_text(f"Loading {gallery}…")
    files = await _list_gallery_files(gallery)
    if not files:
        await query.edit_message_text(f"No files found in {gallery}.")
        return ConversationHandler.END

    context.user_data["remove_files"] = files
    await query.edit_message_text(f"{gallery} — {len(files)} file(s). Sending preview…")
    await _send_remove_preview(update.effective_chat.id, context, 0)
    return REMOVING_FILE


async def _send_remove_preview(chat_id: int, context: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    files = context.user_data["remove_files"]
    gallery = context.user_data["remove_gallery"]
    total = len(files)

    if idx >= total:
        await context.bot.send_message(chat_id, "No more files.\n\n/remove to start over · send a photo to upload")
        return

    file_info = files[idx]
    filename = file_info["name"]
    ext = filename.rsplit(".", 1)[-1].lower()
    caption = f"{idx + 1} / {total}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Delete", callback_data=f"rd:del:{idx}"),
        InlineKeyboardButton("→ Next",   callback_data=f"rd:nxt:{idx}"),
        InlineKeyboardButton("✓ Done",   callback_data=f"rd:done:{idx}"),
    ]])

    raw_url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
        f"/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(filename)}"
    )

    if ext in _VIDEO_EXTS:
        await context.bot.send_message(chat_id, f"📹 {caption}\n{filename}", reply_markup=keyboard)
    else:
        try:
            await context.bot.send_photo(chat_id, photo=raw_url, caption=caption, reply_markup=keyboard)
        except Exception:
            await context.bot.send_message(chat_id, f"🖼 {caption}\n{filename}", reply_markup=keyboard)


async def remove_file_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")   # "rd", action, idx
    action = parts[1]
    file_idx = int(parts[2])

    # Remove keyboard from the tapped message
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "done":
        await query.message.reply_text("Done.\n\n/remove to delete more · send a photo to upload")
        return ConversationHandler.END

    files = context.user_data["remove_files"]
    gallery = context.user_data["remove_gallery"]

    if action == "del":
        file_info = files[file_idx]
        filename = file_info["name"]
        file_sha = file_info["sha"]

        deleting_msg = await query.message.reply_text(f"Deleting…")
        ok, err = await _gh_delete_file(
            f"assets/{gallery}/{filename}", file_sha, f"Remove {filename} from {gallery}"
        )
        if not ok:
            await deleting_msg.edit_text(f"Delete failed: {err}")
            return REMOVING_FILE

        html_rel = _html_rel_path(gallery)
        current_html, html_sha = await _gh_get_file(html_rel)
        if current_html:
            new_html = _remove_from_gallery_html(current_html, gallery, filename)
            if new_html != current_html:
                await _gh_put_file(html_rel, new_html, f"Remove {filename}", sha=html_sha)

        await deleting_msg.edit_text(f"✓ Deleted.")
        files.pop(file_idx)
        next_idx = file_idx  # next file slides into same position

    else:  # nxt
        next_idx = file_idx + 1

    await _send_remove_preview(update.effective_chat.id, context, next_idx)
    return REMOVING_FILE


def _unescape_js(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\").replace("\\n", "\n")


async def cmd_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    galleries = await _existing_galleries()
    if not galleries:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    context.user_data["cap_galleries"] = galleries
    keyboard = [[InlineKeyboardButton(g, callback_data=f"cg:{i}")] for i, g in enumerate(galleries)]
    await update.message.reply_text("Edit captions in which gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CAPTION_GALLERY


async def caption_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    gallery = context.user_data["cap_galleries"][idx]
    context.user_data["cap_gallery"] = gallery

    await query.edit_message_text(f"Loading {gallery}…")
    current_html, html_sha = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await query.edit_message_text("Could not load gallery HTML.")
        return ConversationHandler.END

    text = current_html.decode("utf-8")
    filenames = _get_js_array_entries(text, "filenames")
    captions = _get_js_array_entries(text, "captions")
    while len(captions) < len(filenames):
        captions.append("")

    if not filenames:
        await query.edit_message_text(f"No photos found in {gallery}.")
        return ConversationHandler.END

    context.user_data["cap_filenames"] = filenames
    context.user_data["cap_captions"] = captions  # stored as JS-escaped strings

    await query.edit_message_text(f"{gallery} — {len(filenames)} photo(s). Sending preview…")
    await _send_caption_preview(update.effective_chat.id, context, 0)
    return CAPTION_FILE


async def _send_caption_preview(chat_id: int, context: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    filenames = context.user_data["cap_filenames"]
    captions = context.user_data["cap_captions"]
    gallery = context.user_data["cap_gallery"]
    total = len(filenames)

    if idx >= total:
        await context.bot.send_message(chat_id, "All photos reviewed.\n\n/caption to edit more · send a photo to upload")
        return

    filename = filenames[idx]
    current_cap = _unescape_js(captions[idx]) if captions[idx] else ""
    ext = filename.rsplit(".", 1)[-1].lower()

    tg_caption = f"{idx + 1} / {total}"
    if current_cap:
        tg_caption += f"\n📝 {current_cap[:200]}{'…' if len(current_cap) > 200 else ''}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data=f"ce:edit:{idx}"),
        InlineKeyboardButton("→ Next",  callback_data=f"ce:nxt:{idx}"),
        InlineKeyboardButton("✓ Done",  callback_data=f"ce:done:{idx}"),
    ]])

    raw_url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
        f"/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(filename)}"
    )

    if ext in _VIDEO_EXTS:
        await context.bot.send_message(chat_id, f"📹 {tg_caption}\n{filename}", reply_markup=keyboard)
    else:
        try:
            await context.bot.send_photo(chat_id, photo=raw_url, caption=tg_caption, reply_markup=keyboard)
        except Exception:
            await context.bot.send_message(chat_id, f"🖼 {tg_caption}\n{filename}", reply_markup=keyboard)


async def caption_file_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]
    file_idx = int(parts[2])

    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "done":
        await query.message.reply_text("Done.\n\n/caption to edit more · send a photo to upload")
        return ConversationHandler.END

    if action == "nxt":
        await _send_caption_preview(update.effective_chat.id, context, file_idx + 1)
        return CAPTION_FILE

    # action == "edit"
    context.user_data["cap_edit_idx"] = file_idx
    total = len(context.user_data["cap_filenames"])
    await query.message.reply_text(
        f"Type the new caption for photo {file_idx + 1} / {total}:\n(or /skip to clear it)"
    )
    return CAPTION_TEXT


async def caption_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _apply_caption_edit(update, context, update.message.text.strip())


async def caption_skip_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _apply_caption_edit(update, context, "")


async def _apply_caption_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, new_caption: str) -> int:
    idx = context.user_data["cap_edit_idx"]
    gallery = context.user_data["cap_gallery"]
    filenames = context.user_data["cap_filenames"]
    captions = context.user_data["cap_captions"]

    captions[idx] = _safe_js(new_caption)  # escape and store
    context.user_data["cap_captions"] = captions

    # Always fetch fresh HTML + SHA before saving to avoid conflicts
    current_html, html_sha = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await update.message.reply_text("Failed to fetch gallery HTML.")
        return CAPTION_FILE

    text = current_html.decode("utf-8")
    text = _set_js_array(text, "captions", captions)
    ok, err = await _gh_put_file(
        _html_rel_path(gallery), text.encode("utf-8"),
        f"Update caption for {filenames[idx]} in {gallery}",
        sha=html_sha,
    )
    if not ok:
        await update.message.reply_text(f"Save failed: {err}")
        return CAPTION_FILE

    label = "Caption updated." if new_caption else "Caption cleared."
    await update.message.reply_text(label)
    await _send_caption_preview(update.effective_chat.id, context, idx + 1)
    return CAPTION_FILE


# ---------------------------------------------------------------------------
# /photo — pick a specific photo, download it, edit its caption
# ---------------------------------------------------------------------------

async def cmd_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    galleries = await _existing_galleries()
    if not galleries:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    context.user_data["ph_galleries"] = galleries
    keyboard = [[InlineKeyboardButton(g, callback_data=f"pg:{i}")] for i, g in enumerate(galleries)]
    await update.message.reply_text("Pick a gallery:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PHOTO_GALLERY


async def photo_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    gallery = context.user_data["ph_galleries"][idx]
    context.user_data["ph_gallery"] = gallery

    await query.edit_message_text(f"Loading {gallery}…")
    current_html, _ = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await query.edit_message_text("Could not load gallery HTML.")
        return ConversationHandler.END

    text = current_html.decode("utf-8")
    filenames = _get_js_array_entries(text, "filenames")
    captions = _get_js_array_entries(text, "captions")
    while len(captions) < len(filenames):
        captions.append("")

    if not filenames:
        await query.edit_message_text(f"No photos in {gallery}.")
        return ConversationHandler.END

    context.user_data["ph_filenames"] = filenames
    context.user_data["ph_captions"] = captions

    # Send all photos numbered so user can see what to pick
    chat_id = update.effective_chat.id
    n = len(filenames)
    await query.edit_message_text(f"{gallery} — {n} photo(s). Sending previews…")

    for i, fn in enumerate(filenames):
        raw_url = (
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
            f"/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(fn)}"
        )
        cap_preview = _unescape_js(captions[i]) if captions[i] else ""
        tg_cap = f"{i + 1} / {n}"
        if cap_preview:
            tg_cap += f"\n📝 {cap_preview[:120]}{'…' if len(cap_preview) > 120 else ''}"
        ext = fn.rsplit(".", 1)[-1].lower()
        if ext in _VIDEO_EXTS:
            await context.bot.send_message(chat_id, f"📹 {tg_cap}\n{fn}")
        else:
            try:
                await context.bot.send_photo(chat_id, photo=raw_url, caption=tg_cap)
            except Exception:
                await context.bot.send_message(chat_id, f"🖼 {tg_cap}\n{fn}")

    await context.bot.send_message(
        chat_id,
        f"Which photo? Reply with a number (1–{n}):",
    )
    return PHOTO_NUMBER


async def photo_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    filenames = context.user_data.get("ph_filenames", [])
    gallery = context.user_data.get("ph_gallery", "")
    captions = context.user_data.get("ph_captions", [])
    n = len(filenames)

    try:
        pick = int(update.message.text.strip())
        if not 1 <= pick <= n:
            raise ValueError
    except ValueError:
        await update.message.reply_text(f"Enter a number between 1 and {n}:")
        return PHOTO_NUMBER

    idx = pick - 1
    context.user_data["ph_idx"] = idx
    return await _send_photo_action(update.effective_chat.id, context, idx)


async def _send_photo_action(chat_id: int, context: ContextTypes.DEFAULT_TYPE, idx: int) -> int:
    filenames = context.user_data["ph_filenames"]
    captions = context.user_data["ph_captions"]
    gallery = context.user_data["ph_gallery"]
    filename = filenames[idx]
    current_cap = _unescape_js(captions[idx]) if captions[idx] else ""
    n = len(filenames)

    raw_url = (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
        f"/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(filename)}"
    )

    cap_line = f"📝 {current_cap}" if current_cap else "No caption yet."
    tg_cap = f"{idx + 1} / {n} — {filename}\n{cap_line}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit Caption", callback_data=f"pa:edit:{idx}"),
        InlineKeyboardButton("✓ Done",          callback_data=f"pa:done:{idx}"),
    ]])

    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in _VIDEO_EXTS:
        await context.bot.send_message(chat_id, f"📹 {tg_cap}", reply_markup=keyboard)
    else:
        try:
            # send_document gives full-resolution downloadable file
            await context.bot.send_document(chat_id, document=raw_url, caption=tg_cap, reply_markup=keyboard)
        except Exception:
            try:
                await context.bot.send_photo(chat_id, photo=raw_url, caption=tg_cap, reply_markup=keyboard)
            except Exception:
                await context.bot.send_message(chat_id, tg_cap, reply_markup=keyboard)

    return PHOTO_ACTION


async def photo_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action, idx = parts[1], int(parts[2])

    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "done":
        await query.message.reply_text("Done. /photo to grab another · send a photo to upload.")
        return ConversationHandler.END

    # action == "edit"
    context.user_data["ph_idx"] = idx
    filename = context.user_data["ph_filenames"][idx]
    await query.message.reply_text(
        f"Type the new caption for photo {idx + 1} ({filename}):\n(or /skip to clear it)"
    )
    return PHOTO_ACTION


async def photo_caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _apply_photo_caption(update, context, update.message.text.strip())


async def photo_caption_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _apply_photo_caption(update, context, "")


async def _apply_photo_caption(update: Update, context: ContextTypes.DEFAULT_TYPE, new_caption: str) -> int:
    idx = context.user_data["ph_idx"]
    gallery = context.user_data["ph_gallery"]
    filenames = context.user_data["ph_filenames"]
    captions = context.user_data["ph_captions"]

    captions[idx] = _safe_js(new_caption)
    context.user_data["ph_captions"] = captions

    current_html, html_sha = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await update.message.reply_text("Failed to fetch gallery HTML.")
        return await _send_photo_action(update.effective_chat.id, context, idx)

    text = current_html.decode("utf-8")
    text = _set_js_array(text, "captions", captions)
    ok, err = await _gh_put_file(
        _html_rel_path(gallery), text.encode("utf-8"),
        f"Update caption for {filenames[idx]} in {gallery}",
        sha=html_sha,
    )
    if not ok:
        await update.message.reply_text(f"Save failed: {err}")
    else:
        label = "Caption saved." if new_caption else "Caption cleared."
        await update.message.reply_text(label)

    return await _send_photo_action(update.effective_chat.id, context, idx)


async def cmd_reorder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    galleries = await _existing_galleries()
    if not galleries:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    context.user_data["reorder_galleries"] = galleries
    keyboard = [[InlineKeyboardButton(g, callback_data=f"ro:{i}")] for i, g in enumerate(galleries)]
    await update.message.reply_text("Reorder which gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
    return REORDER_GALLERY


async def reorder_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    gallery = context.user_data["reorder_galleries"][idx]
    context.user_data["reorder_gallery"] = gallery

    await query.edit_message_text(f"Loading {gallery}…")

    current_html, _ = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await query.edit_message_text(f"Could not load {gallery} HTML.")
        return ConversationHandler.END

    text = current_html.decode("utf-8")
    filenames = _get_js_array_entries(text, "filenames")
    if not filenames:
        await query.edit_message_text(
            f"{gallery} doesn't use the slideshow format — can't reorder it here."
        )
        return ConversationHandler.END

    context.user_data["reorder_filenames"] = filenames
    n = len(filenames)
    chat_id = update.effective_chat.id

    await query.edit_message_text(f"Sending {n} photos — scroll up after they load, then reply with the new order.")

    for i, fn in enumerate(filenames):
        raw_url = (
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
            f"/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(fn)}"
        )
        ext = fn.rsplit(".", 1)[-1].lower()
        caption = f"{i + 1} / {n}"
        if ext in _VIDEO_EXTS:
            await context.bot.send_message(chat_id, f"📹 {caption}\n{fn}")
        else:
            try:
                await context.bot.send_photo(chat_id, photo=raw_url, caption=caption)
            except Exception:
                await context.bot.send_message(chat_id, f"🖼 {caption}\n{fn}")

    await context.bot.send_message(
        chat_id,
        f"Photos above are numbered 1–{n}.\n\n"
        f"Reply with the new order — numbers only, space-separated.\n"
        f"Example: <code>3 1 2 4 5</code>\n\n"
        f"All {n} numbers required. /cancel to quit.",
        parse_mode="HTML",
    )
    return REORDER_ORDER


async def reorder_order_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gallery = context.user_data.get("reorder_gallery", "")
    filenames = context.user_data.get("reorder_filenames", [])
    n = len(filenames)

    try:
        positions = [int(x) for x in update.message.text.strip().split()]
    except ValueError:
        await update.message.reply_text(
            f"Numbers only please, e.g.: 3 1 2\nTry again:"
        )
        return REORDER_ORDER

    if sorted(positions) != list(range(1, n + 1)):
        await update.message.reply_text(
            f"Need each number from 1 to {n} exactly once.\n"
            f"Got {len(positions)} numbers. Try again:"
        )
        return REORDER_ORDER

    status = await update.message.reply_text("Saving new order…")

    current_html, html_sha = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await status.edit_text("Failed to fetch gallery HTML.")
        return ConversationHandler.END

    html_text = current_html.decode("utf-8")
    captions = _get_js_array_entries(html_text, "captions")

    new_filenames = [filenames[p - 1] for p in positions]
    if captions and len(captions) == n:
        new_captions = [captions[p - 1] for p in positions]
    else:
        new_captions = captions

    html_text = _set_js_array(html_text, "filenames", new_filenames)
    if new_captions and new_captions != captions:
        html_text = _set_js_array(html_text, "captions", new_captions)

    ok, err = await _gh_put_file(
        _html_rel_path(gallery), html_text.encode("utf-8"),
        f"Reorder photos in {gallery}",
        sha=html_sha,
    )
    if not ok:
        await status.edit_text(f"Save failed: {err}")
        return ConversationHandler.END

    await status.edit_text(f"✓ {gallery} reordered — {n} photos saved.")
    return ConversationHandler.END


def _build_share_html(gallery: str, title: str, filenames: list[str], share_url: str = "") -> bytes:
    safe_title = _safe_html(title)
    base_path = f"../assets/{gallery}/"
    # Prefer a JPEG for the OG image — better scraper support than PNG
    owner = _repo_owner.lower()
    preview_file = next(
        (f for f in filenames if f.lower().endswith((".jpg", ".jpeg"))),
        filenames[0] if filenames else None,
    )
    first_img = ""
    if preview_file:
        first_img = (
            f"https://{owner}.github.io/{_repo_name}"
            f"/assets/{urllib.parse.quote(gallery, safe='')}/{urllib.parse.quote(preview_file, safe='')}"
        )
    files_json = json.dumps(filenames)
    safe_url = _safe_html(share_url)
    safe_img = _safe_html(first_img)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title} · Sheryl Joyce</title>
  <meta property="og:title" content="{safe_title}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{safe_url}">
  <meta property="og:image" content="{safe_img}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="800">
  <meta property="og:description" content="A gallery by Sheryl Joyce">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:image" content="{safe_img}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Jost:wght@300&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 100%; height: 100%; background: #060404; overflow: hidden; }}
    .shell {{ position: relative; width: 100vw; height: 100vh; }}
    .slide {{ position: absolute; inset: 0; opacity: 0; transition: opacity 0.7s ease; display: flex; align-items: center; justify-content: center; }}
    .slide.active {{ opacity: 1; }}
    .slide img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
    .slide.active img {{ animation: kb 9s ease-in-out forwards; }}
    @keyframes kb {{ from {{ transform: scale(1.0); }} to {{ transform: scale(1.08); }} }}
    .top {{ position: absolute; top: 0; left: 0; right: 0; z-index: 10; padding: 1.2rem 1.5rem; background: linear-gradient(to bottom, rgba(0,0,0,0.6), transparent); pointer-events: none; }}
    .top h1 {{ font-family: 'Cormorant Garamond', serif; font-size: 1rem; font-weight: 400; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(255,255,255,0.88); }}
    .bottom {{ position: absolute; bottom: 0; left: 0; right: 0; z-index: 10; padding: 1rem 1.5rem; background: linear-gradient(to top, rgba(0,0,0,0.6), transparent); display: flex; justify-content: space-between; align-items: flex-end; pointer-events: none; }}
    .counter {{ font-family: 'Jost', sans-serif; font-size: 0.72rem; letter-spacing: 0.1em; color: rgba(255,255,255,0.38); }}
    .credit {{ font-family: 'Cormorant Garamond', serif; font-size: 0.72rem; letter-spacing: 0.22em; text-transform: uppercase; color: rgba(255,255,255,0.32); }}
    .ctrl {{ position: absolute; top: 50%; transform: translateY(-50%); z-index: 10; width: 2.8rem; height: 2.8rem; border: 1px solid rgba(255,255,255,0.3); border-radius: 50%; background: rgba(0,0,0,0.2); color: rgba(255,255,255,0.75); font-size: 1.5rem; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.2s; }}
    .ctrl:hover {{ background: rgba(255,255,255,0.1); }}
    #prev {{ left: 1rem; }}
    #next {{ right: 1rem; }}
    @media (max-width: 600px) {{ .ctrl {{ width: 2.2rem; height: 2.2rem; font-size: 1.2rem; }} }}
  </style>
</head>
<body>
  <div class="shell" id="shell">
    <div class="top"><h1>{safe_title}</h1></div>
    <button class="ctrl" id="prev" aria-label="Previous">&#8249;</button>
    <button class="ctrl" id="next" aria-label="Next">&#8250;</button>
    <div class="bottom">
      <span class="counter" id="counter"></span>
      <span class="credit">Sheryl Joyce</span>
    </div>
  </div>
  <script>
    (function () {{
      var BASE = {json.dumps(base_path)};
      var files = {files_json};
      var shell = document.getElementById('shell');
      var counter = document.getElementById('counter');
      var top = document.querySelector('.top');
      var cur = 0, slides = [];
      files.forEach(function (fn, i) {{
        var d = document.createElement('div');
        d.className = 'slide' + (i === 0 ? ' active' : '');
        var img = document.createElement('img');
        img.src = BASE + encodeURIComponent(fn);
        img.alt = '';
        d.appendChild(img);
        shell.insertBefore(d, top);
        slides.push(d);
      }});
      function show(n) {{
        slides[cur].classList.remove('active');
        cur = (n + slides.length) % slides.length;
        slides[cur].classList.add('active');
        counter.textContent = (cur + 1) + ' / ' + slides.length;
      }}
      document.getElementById('prev').onclick = function () {{ show(cur - 1); }};
      document.getElementById('next').onclick = function () {{ show(cur + 1); }};
      window.addEventListener('keydown', function (e) {{
        if (e.key === 'ArrowLeft') show(cur - 1);
        if (e.key === 'ArrowRight') show(cur + 1);
      }});
      show(0);
    }})();
  </script>
</body>
</html>"""
    return html.encode("utf-8")


async def cmd_share(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    galleries = await _existing_galleries()
    if not galleries:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    context.user_data["share_galleries"] = galleries
    keyboard = [[InlineKeyboardButton(g, callback_data=f"sh:{i}")] for i, g in enumerate(galleries)]
    await update.message.reply_text("Share page for which gallery?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SHARE_GALLERY


async def share_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    idx = int(query.data[3:])
    gallery = context.user_data["share_galleries"][idx]

    await query.edit_message_text(f"Building share page for {gallery}…")

    current_html, _ = await _gh_get_file(_html_rel_path(gallery))
    if not current_html:
        await query.edit_message_text(f"Could not load {gallery} HTML.")
        return ConversationHandler.END

    text = current_html.decode("utf-8")
    filenames = _get_js_array_entries(text, "filenames")
    if not filenames:
        await query.edit_message_text(f"{gallery} has no photos yet.")
        return ConversationHandler.END

    title_m = re.search(r"<title>([^<]+)", text)
    title = title_m.group(1).split("·")[0].strip() if title_m else gallery.replace("-", " ").title()

    share_rel = f"s/{gallery.lower()}.html"
    share_url = f"{GITHUB_PAGES_URL}/{share_rel}"
    share_html = _build_share_html(gallery, title, filenames, share_url=share_url)
    _, existing_sha = await _gh_get_file(share_rel)
    ok, err = await _gh_put_file(share_rel, share_html, f"Share page: {gallery}", sha=existing_sha)
    if not ok:
        await query.edit_message_text(f"Failed to create share page: {err}")
        return ConversationHandler.END

    await query.edit_message_text(
        f"✓ Share page ready!\n\n"
        f"{share_url}\n\n"
        f"⏱ Wait ~5 minutes for GitHub to deploy, then paste the link.\n"
        f"If WhatsApp shows no preview, paste it in a brand-new chat — "
        f"WhatsApp caches 'no preview' per conversation and won't re-check."
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    persistence = PicklePersistence(filepath="/tmp/joyce_bot_state.pkl")
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    _media_filter = filters.PHOTO | filters.VIDEO | filters.Document.IMAGE | filters.Document.VIDEO

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(_media_filter, photo_received),
            CommandHandler("remove", cmd_remove),
            CommandHandler("caption", cmd_caption),
            CommandHandler("feature", cmd_feature),
            CommandHandler("fcaption", cmd_fcaption),
            CommandHandler("reorder", cmd_reorder),
            CommandHandler("photo", cmd_photo),
            CommandHandler("share", cmd_share),
        ],
        states={
            CHOOSING_GALLERY:        [
                CallbackQueryHandler(gallery_chosen, pattern=r"^g:"),
                MessageHandler(_media_filter, photo_received),
            ],
            NAMING_GALLERY:          [MessageHandler(filters.TEXT & ~filters.COMMAND, gallery_named)],
            CHOOSING_FRIEND_GALLERY: [CallbackQueryHandler(friend_gallery_chosen, pattern=r"^f:")],
            NAMING_FRIEND_GALLERY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, friend_gallery_named)],
            CHOOSING_ULTRA_GALLERY:  [CallbackQueryHandler(ultra_gallery_chosen, pattern=r"^u:")],
            NAMING_ULTRA_GALLERY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ultra_gallery_named)],
            CHOOSING_SENZA_GALLERY:  [CallbackQueryHandler(senza_gallery_chosen, pattern=r"^z:")],
            NAMING_SENZA_GALLERY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, senza_gallery_named)],
            ADDING_CAPTION:          [
                CommandHandler("skip", caption_skipped),
                CallbackQueryHandler(skip_caption_button, pattern=rf"^{_SKIP_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_received),
            ],
            ADDING_MORE:             [
                MessageHandler(_media_filter, more_photo_received),
                CommandHandler("done", cmd_done),
            ],
            REMOVING_GALLERY:        [CallbackQueryHandler(remove_gallery_chosen, pattern=r"^rg:")],
            REMOVING_FILE:           [CallbackQueryHandler(remove_file_action, pattern=r"^rd:")],
            CAPTION_GALLERY:         [CallbackQueryHandler(caption_gallery_chosen, pattern=r"^cg:")],
            CAPTION_FILE:            [CallbackQueryHandler(caption_file_action, pattern=r"^ce:")],
            CAPTION_TEXT:            [
                CommandHandler("skip", caption_skip_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_text_received),
            ],
            FEATURE_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, feature_title_received)],
            FEATURE_PHOTOS:  [
                MessageHandler(_media_filter, feature_photo_received),
                CommandHandler("done", feature_ask_caption),
            ],
            FEATURE_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, feature_caption_received),
                CommandHandler("done", feature_caption_done),
            ],
            FCAP_CHOOSE: [CallbackQueryHandler(fcap_page_chosen, pattern=r"^fc:")],
            REORDER_GALLERY: [CallbackQueryHandler(reorder_gallery_chosen, pattern=r"^ro:")],
            REORDER_ORDER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, reorder_order_received)],
            SHARE_GALLERY:   [CallbackQueryHandler(share_gallery_chosen, pattern=r"^sh:")],
            PHOTO_GALLERY:   [CallbackQueryHandler(photo_gallery_chosen, pattern=r"^pg:")],
            PHOTO_NUMBER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, photo_number_received)],
            PHOTO_ACTION:    [
                CallbackQueryHandler(photo_action, pattern=r"^pa:"),
                CommandHandler("skip", photo_caption_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, photo_caption_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        name="main_conv",
        persistent=True,
        allow_reentry=True,
        conversation_timeout=1800,
    )

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Unhandled exception: %s", context.error, exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(f"An error occurred: {context.error}")
            except Exception:
                pass

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("galleries", cmd_galleries))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(conv)
    app.add_error_handler(error_handler)

    PORT = int(os.environ.get("PORT", 8080))
    uvicorn_config = uvicorn.Config(portrait_api, host="0.0.0.0", port=PORT, log_level="warning")
    web_server = uvicorn.Server(uvicorn_config)

    async def _run() -> None:
        async with app:
            await app.start()
            from telegram import BotCommand
            await app.bot.set_my_commands([
                BotCommand("galleries", "List existing galleries"),
                BotCommand("remove",    "Delete a photo or video from a gallery"),
                BotCommand("caption",   "Edit photo captions in a gallery"),
                BotCommand("reorder",   "Rearrange photo order in a gallery"),
                BotCommand("feature",   "Create a featured page for Joyce Ultra"),
                BotCommand("fcaption",  "Update caption on a featured page"),
                BotCommand("sync",      "Post all existing photos to the channel"),
                BotCommand("done",      "Finish a batch upload"),
                BotCommand("share",     "Generate a standalone shareable gallery link"),
                BotCommand("cancel",    "Cancel current operation"),
            ])
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot polling · Portrait API on :%d", PORT)
            await web_server.serve()
            await app.updater.stop()
            await app.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
