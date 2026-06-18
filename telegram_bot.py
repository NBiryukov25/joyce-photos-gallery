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
import os
import re
import logging
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
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
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")

_repo_owner, _repo_name = GITHUB_REPO.split("/", 1)
GITHUB_PAGES_URL = f"https://{_repo_owner}.github.io/{_repo_name}"

CHOOSING_GALLERY, NAMING_GALLERY, CHOOSING_FRIEND_GALLERY, NAMING_FRIEND_GALLERY, ADDING_CAPTION, ADDING_MORE, REMOVING_GALLERY, REMOVING_FILE, CAPTION_GALLERY, CAPTION_FILE, CAPTION_TEXT = range(11)

SPECIAL_HTML: dict[str, str] = {}

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
    timeout = httpx.Timeout(connect=10.0, write=30.0, read=30.0, pool=5.0)
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

_SKIP_DIRS = {"videos", "audio", "Gallery_photos", "Joyce-and-Friends"}


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


def _make_filename(use_original: bool, original_name: str, is_video: bool = False) -> str:
    if use_original:
        return original_name
    ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    return f"video-{ts}.mp4" if is_video else f"photo-{ts}.jpg"


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
        asset_path = re.escape(f"assets/{gallery}/{filename}")
        text = re.sub(
            rf'\n\s*<div class="photo-item">\n\s*<(?:img|video)[^>]*src="{asset_path}"[^>]*>(?:</video>)?\n\s*<div class="photo-label">[^<]*</div>\n\s*</div>',
            "",
            text,
        )

    return text.encode("utf-8")


def _updated_html(current: bytes, gallery: str, filename: str, caption: str) -> bytes:
    text = current.decode("utf-8")

    if re.search(r"var filenames\s*=\s*\[", text):
        # Slideshow gallery: update JS arrays
        text = _insert_into_js_array(text, "filenames", filename)
        if re.search(r"var captions\s*=\s*\[", text):
            text = _insert_into_js_array(text, "captions", caption)
    elif re.search(r'class="photo-grid"', text):
        # Photo-grid gallery: append a photo-item div (or video element)
        asset_path = f"assets/{gallery}/{filename}"
        label = _safe_html(caption if caption else filename)
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in _VIDEO_EXTS:
            media_tag = (
                f'        <video controls src="{asset_path}"'
                f' style="width:100%;display:block;border-radius:4px;"></video>'
            )
        else:
            media_tag = (
                f'        <img src="{asset_path}" alt="{_safe_html(caption or "Photo")}"'
                f' data-caption="{_safe_html(caption)}">'
            )
        new_item = (
            f'\n      <div class="photo-item">\n'
            f'{media_tag}\n'
            f'        <div class="photo-label">{label}</div>\n'
            f'      </div>'
        )
        text = re.sub(
            r'(\n\n    </div>\n\n  </div>)',
            new_item + r'\1',
            text,
            count=1,
        )

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

    try:
        galleries = await _existing_galleries()
        regular = [g for g in galleries if not g.startswith("Friends-")]
        keyboard = [[InlineKeyboardButton(g, callback_data=f"g:{g}")] for g in regular]
        keyboard.append([InlineKeyboardButton("Friends →", callback_data="g:__friends__")])
        keyboard.append([InlineKeyboardButton("+ New Gallery", callback_data="g:__new__")])
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

    context.user_data["gallery"] = choice
    await query.edit_message_text(f"Adding to {choice}.\n\nCaption? (or /skip)")
    return ADDING_CAPTION


async def friend_gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]  # strips "f:"
    if choice == "__new__":
        await query.edit_message_text("Name this friend group (e.g. Nicole, Maria):")
        return NAMING_FRIEND_GALLERY
    context.user_data["gallery"] = choice
    name = choice.replace("Friends-", "").replace("-", " ").title()
    await query.edit_message_text(f"Adding to {name}.\n\nCaption? (or /skip)")
    return ADDING_CAPTION


async def friend_gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "Friend"
    gallery = f"Friends-{name}"
    context.user_data["gallery"] = gallery
    await update.message.reply_text(f"New friend gallery: {name.replace('-', ' ')}\n\nCaption? (or /skip)")
    return ADDING_CAPTION


async def gallery_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    name = re.sub(r"[^\w\-]", "-", raw).strip("-") or "New-Gallery"
    context.user_data["gallery"] = name
    await update.message.reply_text(f"Gallery: {name}\n\nCaption? (or /skip)")
    return ADDING_CAPTION


async def caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = update.message.text.strip()
    return await _finalize(update, context)


async def caption_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = ""
    return await _finalize(update, context)


async def more_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    err = _store_media(update.message, context)
    if err:
        await update.message.reply_text(err)
        return ConversationHandler.END
    gallery = context.user_data.get("gallery", "")
    display = gallery.replace("Friends-", "").replace("-", " ") if gallery.startswith("Friends-") else gallery
    kind = "video" if context.user_data.get("is_video") else "photo"
    await update.message.reply_text(f"Adding {kind} to {display}.\n\nCaption? (or /skip)")
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
            await update.message.reply_text(f"Error: {exc}")
        except Exception:
            pass
        return ConversationHandler.END


async def _finalize_inner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gallery   = context.user_data["gallery"]
    caption   = context.user_data.get("caption", "")
    file_id   = context.user_data["file_id"]
    use_orig  = context.user_data.get("use_original", False)
    orig_name = context.user_data.get("original_name", "photo.jpg")
    is_video  = context.user_data.get("is_video", False)

    kind = "video" if is_video else "photo"
    status = await update.message.reply_text(f"Downloading {kind}...")

    suffix = ".mp4" if is_video else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    tg_file = await context.bot.get_file(file_id)
    await asyncio.wait_for(tg_file.download_to_drive(str(tmp_path)), timeout=60)
    raw_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    if is_video:
        upload_bytes = raw_bytes
        kb = len(upload_bytes) // 1024
        logger.info("Video upload: %d KB", kb)
    else:
        await status.edit_text("Compressing photo...")
        upload_bytes = _compress_photo(raw_bytes)
        kb = len(upload_bytes) // 1024
        logger.info("Compressed photo: %d KB (was %d KB)", kb, len(raw_bytes) // 1024)

    filename  = _make_filename(use_orig, orig_name, is_video=is_video)
    photo_rel = f"assets/{gallery}/{filename}"

    await status.edit_text(f"Uploading {kind} to GitHub ({kb} KB)...")

    ok, err = await _gh_put_file(photo_rel, upload_bytes, f"Add {filename} to {gallery}")
    if not ok:
        await status.edit_text(f"Upload failed: {err}")
        return ConversationHandler.END

    await status.edit_text("Updating gallery page...")

    html_rel = _html_rel_path(gallery)
    current_html, html_sha = await _gh_get_file(html_rel)

    if current_html is not None:
        new_html = _updated_html(current_html, gallery, filename, caption)
    else:
        template, _ = await _gh_get_file("galleries/_template-gallery.html")
        if not template:
            await status.edit_text("Could not find gallery template.")
            return ConversationHandler.END
        new_html = _new_gallery_html(template, gallery, filename, caption)

    ok, err = await _gh_put_file(html_rel, new_html, f"Update {gallery} — add {filename}", sha=html_sha)
    if not ok:
        await status.edit_text(f"Photo uploaded but page update failed: {err}")
        return ConversationHandler.END

    # New gallery → add a card to friends.html index
    if html_sha is None:
        friends_html, friends_sha = await _gh_get_file("friends.html")
        if friends_html:
            updated_friends = _update_friends_index(friends_html, gallery, filename)
            if updated_friends != friends_html:
                await _gh_put_file(
                    "friends.html", updated_friends,
                    f"Add {gallery} gallery card to friends page",
                    sha=friends_sha,
                )

    gallery_url = f"{GITHUB_PAGES_URL}/{html_rel}"
    display = gallery.replace("Friends-", "").replace("-", " ") if gallery.startswith("Friends-") else gallery

    # Post to Telegram channel if configured
    channel_note = ""
    if TELEGRAM_CHANNEL:
        try:
            chan_caption = caption if caption else None
            if is_video:
                await context.bot.send_video(
                    chat_id=TELEGRAM_CHANNEL,
                    video=upload_bytes,
                    caption=chan_caption,
                )
            else:
                await context.bot.send_photo(
                    chat_id=TELEGRAM_CHANNEL,
                    photo=upload_bytes,
                    caption=chan_caption,
                )
            channel_note = f"\nPosted to {TELEGRAM_CHANNEL} ✓"
        except Exception as e:
            logger.warning("Channel post failed: %s", e)
            channel_note = f"\nChannel post failed: {e}"

    await status.edit_text(
        f"✓ {filename} added to {display}.{channel_note}\n\n"
        f"Gallery: {gallery_url}\n\n"
        f"Send another photo for {display}, or /done to finish."
    )

    return ADDING_MORE


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


async def cmd_cancel(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    _media_filter = filters.PHOTO | filters.VIDEO | filters.Document.IMAGE | filters.Document.VIDEO

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(_media_filter, photo_received),
            CommandHandler("remove", cmd_remove),
            CommandHandler("caption", cmd_caption),
        ],
        states={
            CHOOSING_GALLERY:        [CallbackQueryHandler(gallery_chosen, pattern=r"^g:")],
            NAMING_GALLERY:          [MessageHandler(filters.TEXT & ~filters.COMMAND, gallery_named)],
            CHOOSING_FRIEND_GALLERY: [CallbackQueryHandler(friend_gallery_chosen, pattern=r"^f:")],
            NAMING_FRIEND_GALLERY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, friend_gallery_named)],
            ADDING_CAPTION:          [
                CommandHandler("skip", caption_skipped),
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
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
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

    logger.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
