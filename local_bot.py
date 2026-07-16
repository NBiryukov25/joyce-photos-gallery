#!/usr/bin/env python3
"""
Local Telegram gallery bot — run on your own machine, no server needed.

Setup:
  pip install -r requirements-local.txt
  Copy .env.example to .env and fill in your values
  python local_bot.py

Commands:
  Send a photo  → upload to a gallery
  /remove       → delete a photo or gallery
  /caption      → edit photo captions
  /reorder      → reorder photos
  /galleries    → list all galleries
  /done         → finish adding photos
  /cancel       → cancel current operation
"""

import asyncio
import base64
import io
import logging
import os
import re
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
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

load_dotenv()

# ── config ───────────────────────────────────────────────────────────────────

BOT_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO     = os.environ.get("GITHUB_REPO", "NBiryukov25/joyce-photos-gallery")
GITHUB_BRANCH   = os.environ.get("GITHUB_BRANCH", "main")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")

if not BOT_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN not set — add it to .env")
if not GITHUB_TOKEN:
    raise SystemExit("GITHUB_TOKEN not set — add it to .env")

_owner, _repo = GITHUB_REPO.split("/", 1)
_PAGES_URL = f"https://{_owner.lower()}.github.io/{_repo}"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── conversation states ───────────────────────────────────────────────────────

(
    CHOOSING_GALLERY, NAMING_GALLERY,
    CHOOSING_FRIEND_GALLERY, NAMING_FRIEND_GALLERY,
    CHOOSING_ULTRA_GALLERY,  NAMING_ULTRA_GALLERY,
    CHOOSING_SENZA_GALLERY,  NAMING_SENZA_GALLERY,
    ADDING_CAPTION, ADDING_MORE,
    REMOVING_GALLERY, REMOVING_FILE,
    CAPTION_GALLERY, CAPTION_FILE, CAPTION_TEXT,
    REORDER_GALLERY, REORDER_ORDER,
) = range(17)

_SKIP_CB = "sc"
_SKIP_KB = InlineKeyboardMarkup([[InlineKeyboardButton("Skip Caption →", callback_data=_SKIP_CB)]])

# ── GitHub helpers ────────────────────────────────────────────────────────────

_GH_API = "https://api.github.com"
_GH_H   = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

SPECIAL_HTML = {"Stashed-companion": "galleries/Stashed-companion.html"}


def _html_rel(gallery: str) -> str:
    return SPECIAL_HTML.get(gallery) or f"galleries/{gallery.lower()}.html"


async def _gh_get(rel: str):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel}", headers=_GH_H, params={"ref": GITHUB_BRANCH})
    if r.status_code == 200:
        d = r.json()
        return base64.b64decode(d["content"]), d["sha"]
    return None, None


async def _gh_put(rel: str, content: bytes, msg: str, sha=None):
    body = {"message": msg, "content": base64.b64encode(content).decode(), "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15, write=120, read=60, pool=5)) as c:
            r = await c.put(f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel}", json=body, headers=_GH_H)
        if r.status_code in (200, 201):
            return True, ""
        return False, r.json().get("message", f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


async def _gh_del(rel: str, sha: str, msg: str):
    body = {"message": msg, "sha": sha, "branch": GITHUB_BRANCH}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, write=30, read=30, pool=5)) as c:
            r = await c.request("DELETE", f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel}", json=body, headers=_GH_H)
        if r.status_code == 200:
            return True, ""
        return False, r.json().get("message", f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


_SKIP_DIRS = {"videos", "audio", "Gallery_photos", "Joyce-and-Friends", "Feature", "from-drive"}


async def _galleries() -> list[str]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_GH_API}/repos/{GITHUB_REPO}/contents/assets", headers=_GH_H, params={"ref": GITHUB_BRANCH})
    if r.status_code == 200:
        return sorted(
            i["name"] for i in r.json()
            if i["type"] == "dir" and not i["name"].startswith((".", "Feature-")) and i["name"] not in _SKIP_DIRS
        )
    return []


async def _gallery_files(gallery: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{_GH_API}/repos/{GITHUB_REPO}/contents/assets/{gallery}", headers=_GH_H, params={"ref": GITHUB_BRANCH})
    if r.status_code == 200:
        return sorted((i for i in r.json() if i["type"] == "file"), key=lambda x: x["name"], reverse=True)
    return []

# ── image / filename helpers ──────────────────────────────────────────────────

_VIDEO_EXTS = frozenset({"mp4", "mov", "webm", "m4v", "avi"})


def _compress(data: bytes, max_dim: int = 1600, quality: int = 78) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        s = max_dim / max(w, h)
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _filename(use_orig: bool, orig_name: str, is_video: bool = False, idx: int = 0) -> str:
    if use_orig:
        return orig_name
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    sfx = f"-{idx:02d}" if idx > 0 else ""
    return f"video-{ts}{sfx}.mp4" if is_video else f"photo-{ts}{sfx}.jpg"

# ── HTML helpers ──────────────────────────────────────────────────────────────

def _js(v: str) -> str:
    return v.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "").replace("\n", " ")


def _html(v: str) -> str:
    return v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _js_array(text: str, var: str) -> list[str]:
    m = re.search(rf"var {re.escape(var)}\s*=\s*\[([\s\S]*?)\];", text)
    return re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1)) if m else []


def _set_js_array(text: str, var: str, entries: list[str]) -> str:
    inner = ("\n        " + "\n        ".join(f"'{e}'," for e in entries) + "\n      ") if entries else ""
    return re.sub(rf"var {re.escape(var)}\s*=\s*\[[\s\S]*?\];", f"var {var} = [{inner}];", text)


def _insert_js(text: str, var: str, value: str) -> str:
    def rep(m):
        pre, body, post = m.group(1), m.group(2), m.group(3)
        stripped = body.rstrip()
        if stripped and not stripped.endswith(","):
            stripped += ","
        return pre + stripped + f"\n        '{_js(value)}',\n      " + post
    return re.sub(rf"(var {re.escape(var)}\s*=\s*\[)([\s\S]*?)(\];)", rep, text)


def _slides_filenames(text: str) -> list[str]:
    m = re.search(r"var slides\s*=\s*\[([\s\S]*?)\];", text)
    return re.findall(r"\bfilename:\s*'([^']+)'", m.group(1)) if m else []


def _reorder_slides(text: str, zero_based: list[int]) -> str:
    m = re.search(r"(var slides\s*=\s*\[)([\s\S]*?)(\];)", text)
    if not m:
        return text
    blocks = re.findall(r"\{[^{}]+\}", m.group(2))
    if len(blocks) != len(zero_based):
        return text
    new_blocks = [blocks[i] for i in zero_based]
    im = re.search(r"^(\s*)\{", m.group(2), re.MULTILINE)
    ind = im.group(1) if im else "      "
    new_inner = "\n" + (",\n".join(ind + b for b in new_blocks)) + ",\n    "
    return text[: m.start(2)] + new_inner + text[m.end(2):]


def _remove_from_html(current: bytes, gallery: str, filename: str) -> bytes:
    text = current.decode("utf-8")
    if re.search(r"var filenames\s*=\s*\[", text):
        fns = _js_array(text, "filenames")
        if filename in fns:
            i = fns.index(filename)
            fns.pop(i)
            text = _set_js_array(text, "filenames", fns)
            caps = _js_array(text, "captions")
            if caps and i < len(caps):
                caps.pop(i)
                text = _set_js_array(text, "captions", caps)
    return text.encode("utf-8")


def _add_to_html(current: bytes, gallery: str, filename: str, caption: str, html_rel: str = "") -> bytes:
    text = current.decode("utf-8")
    if re.search(r"var filenames\s*=\s*\[", text):
        text = _insert_js(text, "filenames", filename)
        if re.search(r"var captions\s*=\s*\[", text):
            text = _insert_js(text, "captions", caption)
    return text.encode("utf-8")


_BACK = {
    "gallery": ("../gallery.html",    "← Galleries"),
    "friends": ("../friends.html",    "← Friends"),
    "ultra":   ("../joyce-ultra.html","← Ultra"),
    "senza":   ("../senza-veli.html", "← Senza Veli"),
}


def _new_gallery_html(template: bytes, gallery: str, filename: str, caption: str, target: str = "") -> bytes:
    text = template.decode("utf-8")
    title = gallery.replace("-", " ").title()
    text = text.replace("GALLERY TITLE", title).replace("ASSET-FOLDER-NAME", gallery)
    text = re.sub(r"var filenames\s*=\s*\[[\s\S]*?\];", f"var filenames = [\n        '{_js(filename)}'\n      ];", text)
    if caption:
        text = re.sub(r"var captions\s*=[\s\S]*?(?:\]\s*;|\}\s*\)\s*;)", f"var captions = [\n        '{_js(caption)}'\n      ];", text)
    key = "friends" if gallery.startswith("Friends-") else ("ultra" if gallery.startswith("Ultra-") else (target if target in _BACK else "gallery"))
    href, label = _BACK[key]
    text = re.sub(r'<a class="topbar-btn" href="\.\./[^"]*">←[^<]*</a>', f'<a class="topbar-btn" href="{href}">{label}</a>', text)
    return text.encode("utf-8")


def _add_card_to_index(index_html: bytes, gallery: str, filename: str, insert_marker: str, prefix: str = "") -> bytes:
    text = index_html.decode("utf-8")
    html_path = _html_rel(gallery)
    if html_path in text:
        return index_html
    name = gallery.replace(prefix, "").replace("-", " ").title()
    img = f"assets/{gallery}/{filename}"
    card = (
        f'<div class="gallery-item"><a href="{html_path}"><img src="{img}" alt="{_html(name)}"></a>'
        f'<div class="gallery-caption"><p class="gallery-caption-title">{_html(name)}</p>'
        f'<a class="gallery-view-link" href="{html_path}">View full series →</a></div></div>\n'
    )
    updated = text.replace(insert_marker, card + insert_marker)
    updated = updated.replace('id="new-galleries-label" style="display:none"', 'id="new-galleries-label"')
    return updated.encode("utf-8")


async def _fix_covers(gallery: str, deleted: str, new_html: bytes) -> None:
    fns = _js_array(new_html.decode("utf-8"), "filenames")
    if not fns:
        return
    old = f"assets/{gallery}/{deleted}"
    new = f"assets/{gallery}/{fns[0]}"
    for path in ("gallery.html", "friends.html", "joyce-ultra.html", "senza-veli.html"):
        c, sha = await _gh_get(path)
        if c and old in c.decode("utf-8"):
            await _gh_put(path, c.decode("utf-8").replace(old, new).encode(), f"Fix {gallery} cover", sha=sha)

# ── auth / media ──────────────────────────────────────────────────────────────

def _auth(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    uid = update.effective_user.id if update.effective_user else None
    return str(uid) == ALLOWED_USER_ID.strip()


def _store_media(msg, ctx) -> str | None:
    use_orig, is_video = False, False
    if msg.photo:
        fid, orig = msg.photo[-1].file_id, "photo.jpg"
    elif msg.video:
        fid, orig, is_video = msg.video.file_id, msg.video.file_name or "video.mp4", True
    elif msg.document:
        doc = msg.document
        mime = doc.mime_type or ""
        if mime.startswith("video/"):
            is_video = True
        elif not mime.startswith("image/"):
            return "Please send a photo or video file."
        fid, orig, use_orig = doc.file_id, doc.file_name or ("video.mp4" if is_video else "photo.jpg"), True
    else:
        return "Please send a photo or video file."
    ctx.user_data.update(file_id=fid, original_name=orig, use_original=use_orig, is_video=is_video)
    return None

# ── upload core ───────────────────────────────────────────────────────────────

async def _upload_one(ctx, gallery, html_rel, item, caption, idx, current_html, html_sha, target=""):
    suffix = ".mp4" if item["is_video"] else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    tg_file = await ctx.bot.get_file(item["file_id"])
    await asyncio.wait_for(tg_file.download_to_drive(str(tmp_path)), timeout=60)
    raw = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    data = raw if item["is_video"] else _compress(raw)
    fn = _filename(item["use_original"], item["original_name"], item["is_video"], idx)
    ok, err = await _gh_put(f"assets/{gallery}/{fn}", data, f"Add {fn} to {gallery}")
    if not ok:
        raise RuntimeError(f"Upload failed: {err}")

    if current_html is not None:
        new_html = _add_to_html(current_html, gallery, fn, caption, html_rel)
    else:
        tpl, _ = await _gh_get("galleries/_template-gallery.html")
        if not tpl:
            raise RuntimeError("Gallery template not found.")
        new_html = _new_gallery_html(tpl, gallery, fn, caption, target)

    ok, err = await _gh_put(html_rel, new_html, f"Update {gallery} — add {fn}", sha=html_sha)
    if not ok:
        raise RuntimeError(f"HTML update failed: {err}")
    _, new_sha = await _gh_get(html_rel)
    return fn, new_html, new_sha


async def _finalize(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    gallery = ctx.user_data["gallery"]
    caption = ctx.user_data.get("caption", "")
    target  = ctx.user_data.get("target_page", "gallery")

    pending = ctx.user_data.pop("pending_album", None)
    ctx.user_data.pop("pending_album_id", None)
    items = pending if pending else [{k: ctx.user_data[k] for k in ("file_id", "original_name", "use_original", "is_video")}]

    total  = len(items)
    status = await update.effective_message.reply_text(f"Uploading 1 / {total}…" if total > 1 else "Uploading…")

    html_rel = _html_rel(gallery)
    cur_html, html_sha = await _gh_get(html_rel)
    is_new   = html_sha is None
    uploaded, failed = [], 0

    for i, item in enumerate(items):
        if total > 1:
            try:
                await status.edit_text(f"Uploading {i + 1} / {total}…")
            except Exception:
                pass
        try:
            fn, cur_html, html_sha = await _upload_one(ctx, gallery, html_rel, item, caption, i, cur_html, html_sha, target)
            uploaded.append(fn)
        except Exception as exc:
            logger.exception("Upload failed item %d", i)
            failed += 1

    if not uploaded:
        await status.edit_text("All uploads failed.")
        return ConversationHandler.END

    if is_new:
        first = uploaded[0]
        if gallery.startswith("Friends-"):
            h, sha = await _gh_get("friends.html")
            if h:
                u = _add_card_to_index(h, gallery, first, "<!-- friend-gallery-insert -->", "Friends-")
                if u != h:
                    await _gh_put("friends.html", u, f"Add {gallery} to friends page", sha=sha)
        elif gallery.startswith("Ultra-"):
            h, sha = await _gh_get("joyce-ultra.html")
            if h:
                u = _add_card_to_index(h, gallery, first, "<!-- ultra-gallery-insert -->", "Ultra-")
                if u != h:
                    await _gh_put("joyce-ultra.html", u, f"Add {gallery} to Joyce Ultra", sha=sha)
        elif target == "senza":
            h, sha = await _gh_get("senza-veli.html")
            if h:
                u = _add_card_to_index(h, gallery, first, "<!-- senza-gallery-insert -->")
                if u != h:
                    await _gh_put("senza-veli.html", u, f"Add {gallery} to Senza Veli", sha=sha)
        else:
            h, sha = await _gh_get("gallery.html")
            if h:
                u = _add_card_to_index(h, gallery, first, "<!-- new-gallery-insert -->")
                if u != h:
                    await _gh_put("gallery.html", u, f"Add {gallery} to gallery index", sha=sha)

    ok_count = len(uploaded)
    summary  = f"✓ {ok_count} photo{'s' if ok_count != 1 else ''} added to {gallery}."
    if failed:
        summary += f" ({failed} failed)"
    await status.edit_text(f"{summary}\n\n{_PAGES_URL}/{html_rel}\n\nSend another photo, or /done to finish.")
    return ADDING_MORE

# ── /start /cancel /done /galleries ──────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Gallery bot ready.\n\n"
        "Send a photo/video to upload it\n"
        "/remove — delete a photo\n"
        "/caption — edit captions\n"
        "/reorder — reorder photos\n"
        "/galleries — list galleries\n"
        "/cancel — stop current operation"
    )


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _conv_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await cmd_start(update, ctx)
    return ConversationHandler.END


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Done! Send a photo to start a new upload.")
    return ConversationHandler.END


async def cmd_galleries(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth(update):
        return
    gs = await _galleries()
    await update.message.reply_text(("Galleries:\n\n" + "\n".join(f"• {g}" for g in gs)) if gs else "No galleries found.")

# ── photo upload flow ─────────────────────────────────────────────────────────

async def photo_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _auth(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    err = _store_media(update.message, ctx)
    if err:
        await update.message.reply_text(err)
        return ConversationHandler.END

    album_id = update.message.media_group_id
    if album_id:
        item = {k: ctx.user_data[k] for k in ("file_id", "original_name", "use_original", "is_video")}
        if ctx.user_data.get("pending_album_id") == album_id:
            ctx.user_data["pending_album"].append(item)
            return CHOOSING_GALLERY
        ctx.user_data["pending_album_id"] = album_id
        ctx.user_data["pending_album"] = [item]
    else:
        ctx.user_data.pop("pending_album_id", None)
        ctx.user_data.pop("pending_album", None)

    try:
        gs = await _galleries()
        regular = [g for g in gs if not g.startswith(("Friends-", "Ultra-"))]
        kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"g:{g}")] for g in regular]
        kb.append([InlineKeyboardButton("Galleries →", callback_data="g:__galleries__"), InlineKeyboardButton("Friends →", callback_data="g:__friends__")])
        kb.append([InlineKeyboardButton("Joyce Ultra →", callback_data="g:__ultra__"), InlineKeyboardButton("Senza Veli →", callback_data="g:__senza__")])
        await update.message.reply_text("Which gallery?", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING_GALLERY
    except Exception as exc:
        await update.message.reply_text(f"Error: {exc}")
        return ConversationHandler.END


async def gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data[2:]

    if choice == "__new__":
        await q.edit_message_text("New gallery name? (e.g. Paris-Summer)")
        return NAMING_GALLERY
    if choice == "__galleries__":
        gs = await _galleries()
        main = [g for g in gs if not g.startswith(("Friends-", "Ultra-"))]
        kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"g:{g}")] for g in main]
        kb.append([InlineKeyboardButton("+ New Gallery", callback_data="g:__new__")])
        await q.edit_message_text("Which gallery?", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING_GALLERY
    if choice == "__friends__":
        gs = await _galleries()
        kb = [[InlineKeyboardButton(g.replace("Friends-", "").replace("-", " "), callback_data=f"f:{g}")] for g in gs if g.startswith("Friends-")]
        kb.append([InlineKeyboardButton("+ New Friend Gallery", callback_data="f:__new__")])
        await q.edit_message_text("Which friend gallery?", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING_FRIEND_GALLERY
    if choice == "__ultra__":
        gs = await _galleries()
        kb = [[InlineKeyboardButton(g.replace("Ultra-", "").replace("-", " "), callback_data=f"u:{g}")] for g in gs if g.startswith("Ultra-")]
        kb.append([InlineKeyboardButton("+ New Ultra Gallery", callback_data="u:__new__")])
        await q.edit_message_text("Joyce Ultra gallery?", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING_ULTRA_GALLERY
    if choice == "__senza__":
        gs = await _galleries()
        kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"z:{g}")] for g in gs if not g.startswith(("Friends-", "Ultra-"))]
        kb.append([InlineKeyboardButton("+ New Senza Gallery", callback_data="z:__new__")])
        await q.edit_message_text("Senza Veli gallery?", reply_markup=InlineKeyboardMarkup(kb))
        return CHOOSING_SENZA_GALLERY

    ctx.user_data.update(gallery=choice, target_page="gallery")
    await q.edit_message_text(f"Gallery: {choice}\n\nAdd a caption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def gallery_named(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip().replace(" ", "-")
    ctx.user_data.update(gallery=name, target_page="gallery")
    await update.message.reply_text(f"New gallery: {name}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def friend_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data[2:]
    if choice == "__new__":
        await q.edit_message_text("New friend gallery name? (Friends- will be added)")
        return NAMING_FRIEND_GALLERY
    ctx.user_data.update(gallery=choice, target_page="friends")
    await q.edit_message_text(f"Gallery: {choice}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def friend_gallery_named(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    name = "Friends-" + update.message.text.strip().replace(" ", "-")
    ctx.user_data.update(gallery=name, target_page="friends")
    await update.message.reply_text(f"New friend gallery: {name}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def ultra_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data[2:]
    if choice == "__new__":
        await q.edit_message_text("New Ultra gallery name? (Ultra- will be added)")
        return NAMING_ULTRA_GALLERY
    ctx.user_data.update(gallery=choice, target_page="ultra")
    await q.edit_message_text(f"Gallery: {choice}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def ultra_gallery_named(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    name = "Ultra-" + update.message.text.strip().replace(" ", "-")
    ctx.user_data.update(gallery=name, target_page="ultra")
    await update.message.reply_text(f"New Ultra gallery: {name}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def senza_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data[2:]
    if choice == "__new__":
        await q.edit_message_text("New Senza Veli gallery name?")
        return NAMING_SENZA_GALLERY
    ctx.user_data.update(gallery=choice, target_page="senza")
    await q.edit_message_text(f"Gallery: {choice}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def senza_gallery_named(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip().replace(" ", "-")
    ctx.user_data.update(gallery=name, target_page="senza")
    await update.message.reply_text(f"New Senza Veli gallery: {name}\n\nCaption or skip:", reply_markup=_SKIP_KB)
    return ADDING_CAPTION


async def caption_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["caption"] = update.message.text.strip()
    return await _finalize(update, ctx)


async def caption_skipped(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["caption"] = ""
    return await _finalize(update, ctx)


async def skip_caption_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    ctx.user_data["caption"] = ""
    await update.callback_query.edit_message_text("Uploading…")
    return await _finalize(update, ctx)


async def more_photo_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    err = _store_media(update.message, ctx)
    if err:
        await update.message.reply_text(err)
        return ADDING_MORE
    album_id = update.message.media_group_id
    if album_id:
        item = {k: ctx.user_data[k] for k in ("file_id", "original_name", "use_original", "is_video")}
        if ctx.user_data.get("pending_album_id") == album_id:
            ctx.user_data["pending_album"].append(item)
            return ADDING_MORE
        ctx.user_data["pending_album_id"] = album_id
        ctx.user_data["pending_album"] = [item]
    else:
        ctx.user_data.pop("pending_album_id", None)
        ctx.user_data.pop("pending_album", None)
    ctx.user_data["caption"] = ""
    return await _finalize(update, ctx)

# ── /remove ───────────────────────────────────────────────────────────────────

async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _auth(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    gs = await _galleries()
    if not gs:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    ctx.user_data["remove_galleries"] = gs
    kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"rg:{i}")] for i, g in enumerate(gs)]
    await update.message.reply_text("Remove from which gallery?", reply_markup=InlineKeyboardMarkup(kb))
    return REMOVING_GALLERY


async def remove_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    gallery = ctx.user_data["remove_galleries"][int(q.data[3:])]
    ctx.user_data["remove_gallery"] = gallery
    await q.edit_message_text(f"Loading {gallery}…")
    files = await _gallery_files(gallery)
    if not files:
        await q.edit_message_text(f"No photos in {gallery}.")
        return ConversationHandler.END
    ctx.user_data["remove_files"] = [{"name": f["name"], "sha": f["sha"]} for f in files]
    await _send_remove_preview(update.effective_chat.id, ctx, 0)
    return REMOVING_FILE


async def _send_remove_preview(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    files   = ctx.user_data.get("remove_files", [])
    gallery = ctx.user_data.get("remove_gallery", "")
    total   = len(files)
    if idx >= total:
        await ctx.bot.send_message(chat_id, "All done.")
        return
    filename = files[idx]["name"]
    ext = filename.rsplit(".", 1)[-1].lower()
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Delete", callback_data=f"rd:del:{idx}"),
        InlineKeyboardButton("→ Next",   callback_data=f"rd:nxt:{idx}"),
        InlineKeyboardButton("✓ Done",   callback_data=f"rd:done:{idx}"),
    ]])
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(filename)}"
    caption = f"{idx + 1} / {total}\n{filename}"
    if ext in _VIDEO_EXTS:
        await ctx.bot.send_message(chat_id, f"📹 {caption}", reply_markup=kb)
    else:
        try:
            await ctx.bot.send_photo(chat_id, photo=raw_url, caption=caption, reply_markup=kb)
        except Exception:
            await ctx.bot.send_message(chat_id, f"🖼 {caption}", reply_markup=kb)


async def remove_file_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, action, file_idx = q.data.split(":")
    file_idx = int(file_idx)
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if action == "done":
        await q.message.reply_text("Done.")
        return ConversationHandler.END

    files   = ctx.user_data["remove_files"]
    gallery = ctx.user_data["remove_gallery"]

    if action == "del":
        f = files[file_idx]
        status = await q.message.reply_text("Deleting…")
        ok, err = await _gh_del(f"assets/{gallery}/{f['name']}", f["sha"], f"Remove {f['name']} from {gallery}")
        if not ok:
            await status.edit_text(f"Delete failed: {err}")
            return REMOVING_FILE
        cur_html, html_sha = await _gh_get(_html_rel(gallery))
        if cur_html:
            new_html = _remove_from_html(cur_html, gallery, f["name"])
            if new_html != cur_html:
                await _gh_put(_html_rel(gallery), new_html, f"Remove {f['name']}", sha=html_sha)
            await _fix_covers(gallery, f["name"], new_html)
        await status.edit_text("✓ Deleted.")
        files.pop(file_idx)
        await _send_remove_preview(update.effective_chat.id, ctx, file_idx)
        return REMOVING_FILE

    await _send_remove_preview(update.effective_chat.id, ctx, file_idx + 1)
    return REMOVING_FILE

# ── /caption ──────────────────────────────────────────────────────────────────

def _unesc(v: str) -> str:
    return v.replace("\\'", "'").replace("\\\\", "\\").replace("\\n", "\n")


async def cmd_caption(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _auth(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    gs = await _galleries()
    if not gs:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    ctx.user_data["cap_galleries"] = gs
    kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"cg:{i}")] for i, g in enumerate(gs)]
    await update.message.reply_text("Edit captions in which gallery?", reply_markup=InlineKeyboardMarkup(kb))
    return CAPTION_GALLERY


async def caption_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    gallery = ctx.user_data["cap_galleries"][int(q.data[3:])]
    ctx.user_data["cap_gallery"] = gallery
    await q.edit_message_text(f"Loading {gallery}…")
    cur, _ = await _gh_get(_html_rel(gallery))
    if not cur:
        await q.edit_message_text("Could not load gallery HTML.")
        return ConversationHandler.END
    text = cur.decode("utf-8")
    fns  = _js_array(text, "filenames")
    caps = _js_array(text, "captions")
    while len(caps) < len(fns):
        caps.append("")
    if not fns:
        await q.edit_message_text(f"No photos in {gallery}.")
        return ConversationHandler.END
    ctx.user_data.update(cap_filenames=fns, cap_captions=caps)
    await q.edit_message_text(f"{gallery} — {len(fns)} photo(s). Sending preview…")
    await _cap_preview(update.effective_chat.id, ctx, 0)
    return CAPTION_FILE


async def _cap_preview(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE, idx: int) -> None:
    fns     = ctx.user_data["cap_filenames"]
    caps    = ctx.user_data["cap_captions"]
    gallery = ctx.user_data["cap_gallery"]
    total   = len(fns)
    if idx >= total:
        await ctx.bot.send_message(chat_id, "All photos reviewed. /caption to edit more.")
        return
    fn  = fns[idx]
    cap = _unesc(caps[idx]) if caps[idx] else ""
    ext = fn.rsplit(".", 1)[-1].lower()
    tg_cap = f"{idx + 1} / {total}" + (f"\n📝 {cap[:200]}" if cap else "")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Edit", callback_data=f"ce:edit:{idx}"),
        InlineKeyboardButton("→ Next",  callback_data=f"ce:nxt:{idx}"),
        InlineKeyboardButton("✓ Done",  callback_data=f"ce:done:{idx}"),
    ]])
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/assets/{urllib.parse.quote(gallery)}/{urllib.parse.quote(fn)}"
    if ext in _VIDEO_EXTS:
        await ctx.bot.send_message(chat_id, f"📹 {tg_cap}\n{fn}", reply_markup=kb)
    else:
        try:
            await ctx.bot.send_photo(chat_id, photo=raw_url, caption=tg_cap, reply_markup=kb)
        except Exception:
            await ctx.bot.send_message(chat_id, f"🖼 {tg_cap}\n{fn}", reply_markup=kb)


async def caption_file_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    _, action, file_idx = q.data.split(":")
    file_idx = int(file_idx)
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if action == "done":
        await q.message.reply_text("Done.")
        return ConversationHandler.END
    if action == "nxt":
        await _cap_preview(update.effective_chat.id, ctx, file_idx + 1)
        return CAPTION_FILE
    ctx.user_data["cap_edit_idx"] = file_idx
    total = len(ctx.user_data["cap_filenames"])
    await q.message.reply_text(f"New caption for photo {file_idx + 1} / {total}:\n(or /skip to clear)")
    return CAPTION_TEXT


async def caption_text_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_caption(update, ctx, update.message.text.strip())


async def caption_skip_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_caption(update, ctx, "")


async def _save_caption(update: Update, ctx: ContextTypes.DEFAULT_TYPE, new_cap: str) -> int:
    idx     = ctx.user_data["cap_edit_idx"]
    gallery = ctx.user_data["cap_gallery"]
    fns     = ctx.user_data["cap_filenames"]
    caps    = ctx.user_data["cap_captions"]
    caps[idx] = _js(new_cap)
    ctx.user_data["cap_captions"] = caps
    cur, sha = await _gh_get(_html_rel(gallery))
    if not cur:
        await update.message.reply_text("Failed to fetch gallery HTML.")
        return CAPTION_FILE
    text = _set_js_array(cur.decode("utf-8"), "captions", caps)
    ok, err = await _gh_put(_html_rel(gallery), text.encode(), f"Update caption for {fns[idx]}", sha=sha)
    if not ok:
        await update.message.reply_text(f"Save failed: {err}")
        return CAPTION_FILE
    await update.message.reply_text("Caption updated." if new_cap else "Caption cleared.")
    await _cap_preview(update.effective_chat.id, ctx, idx + 1)
    return CAPTION_FILE

# ── /reorder ──────────────────────────────────────────────────────────────────

async def cmd_reorder(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _auth(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END
    gs = await _galleries()
    if not gs:
        await update.message.reply_text("No galleries found.")
        return ConversationHandler.END
    ctx.user_data["reorder_galleries"] = gs
    kb = [[InlineKeyboardButton(g.replace("-", " "), callback_data=f"ro:{i}")] for i, g in enumerate(gs)]
    await update.message.reply_text("Reorder which gallery?", reply_markup=InlineKeyboardMarkup(kb))
    return REORDER_GALLERY


async def reorder_gallery_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    gallery = ctx.user_data["reorder_galleries"][int(q.data[3:])]
    ctx.user_data["reorder_gallery"] = gallery
    await q.edit_message_text(f"Loading {gallery}…")
    cur, _ = await _gh_get(_html_rel(gallery))
    if not cur:
        await q.edit_message_text("Could not load gallery HTML.")
        return ConversationHandler.END
    text = cur.decode("utf-8")
    slides_fmt = bool(re.search(r"var slides\s*=\s*\[", text))
    ctx.user_data["reorder_slides_format"] = slides_fmt
    fns = _slides_filenames(text) if slides_fmt else _js_array(text, "filenames")
    if not fns:
        await q.edit_message_text("No photos found.")
        return ConversationHandler.END
    ctx.user_data["reorder_filenames"] = fns
    numbered = "\n".join(f"{i + 1}. {fn}" for i, fn in enumerate(fns))
    await q.edit_message_text(
        f"{gallery} — {len(fns)} photos:\n\n{numbered}\n\nReply with new order, e.g.:\n<code>3 1 2</code>\n\n/cancel to quit.",
        parse_mode="HTML",
    )
    return REORDER_ORDER


async def reorder_order_received(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    gallery = ctx.user_data.get("reorder_gallery", "")
    fns     = ctx.user_data.get("reorder_filenames", [])
    n       = len(fns)
    try:
        positions = [int(x) for x in update.message.text.strip().split()]
    except ValueError:
        await update.message.reply_text("Numbers only, e.g.: 3 1 2\nTry again:")
        return REORDER_ORDER
    if sorted(positions) != list(range(1, n + 1)):
        await update.message.reply_text(f"Need each number 1–{n} exactly once. Try again:")
        return REORDER_ORDER

    status = await update.message.reply_text("Saving…")
    cur, sha = await _gh_get(_html_rel(gallery))
    if not cur:
        await status.edit_text("Failed to fetch gallery HTML.")
        return ConversationHandler.END

    text       = cur.decode("utf-8")
    zero_based = [p - 1 for p in positions]
    if ctx.user_data.get("reorder_slides_format"):
        text = _reorder_slides(text, zero_based)
    else:
        caps = _js_array(text, "captions")
        new_fns  = [fns[p - 1] for p in positions]
        new_caps = [caps[p - 1] for p in positions] if caps and len(caps) == n else caps
        text = _set_js_array(text, "filenames", new_fns)
        if new_caps and new_caps != caps:
            text = _set_js_array(text, "captions", new_caps)

    ok, err = await _gh_put(_html_rel(gallery), text.encode(), f"Reorder photos in {gallery}", sha=sha)
    if not ok:
        await status.edit_text(f"Save failed: {err}")
        return ConversationHandler.END
    await status.edit_text(f"✓ {gallery} reordered.")
    return ConversationHandler.END

# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    persistence = PicklePersistence(filepath="local_bot_state.pkl")
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()
    mf  = filters.PHOTO | filters.VIDEO | filters.Document.IMAGE | filters.Document.VIDEO

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(mf, photo_received),
            CommandHandler("remove",  cmd_remove),
            CommandHandler("caption", cmd_caption),
            CommandHandler("reorder", cmd_reorder),
        ],
        states={
            CHOOSING_GALLERY:        [CallbackQueryHandler(gallery_chosen, pattern=r"^g:"), MessageHandler(mf, photo_received)],
            NAMING_GALLERY:          [MessageHandler(filters.TEXT & ~filters.COMMAND, gallery_named)],
            CHOOSING_FRIEND_GALLERY: [CallbackQueryHandler(friend_gallery_chosen, pattern=r"^f:")],
            NAMING_FRIEND_GALLERY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, friend_gallery_named)],
            CHOOSING_ULTRA_GALLERY:  [CallbackQueryHandler(ultra_gallery_chosen, pattern=r"^u:")],
            NAMING_ULTRA_GALLERY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ultra_gallery_named)],
            CHOOSING_SENZA_GALLERY:  [CallbackQueryHandler(senza_gallery_chosen, pattern=r"^z:")],
            NAMING_SENZA_GALLERY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, senza_gallery_named)],
            ADDING_CAPTION:          [
                CommandHandler("skip", caption_skipped),
                CallbackQueryHandler(skip_caption_cb, pattern=rf"^{_SKIP_CB}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_received),
            ],
            ADDING_MORE:             [MessageHandler(mf, more_photo_received), CommandHandler("done", cmd_done)],
            REMOVING_GALLERY:        [CallbackQueryHandler(remove_gallery_chosen, pattern=r"^rg:")],
            REMOVING_FILE:           [CallbackQueryHandler(remove_file_action,    pattern=r"^rd:")],
            CAPTION_GALLERY:         [CallbackQueryHandler(caption_gallery_chosen, pattern=r"^cg:")],
            CAPTION_FILE:            [CallbackQueryHandler(caption_file_action,    pattern=r"^ce:")],
            CAPTION_TEXT:            [
                CommandHandler("skip", caption_skip_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_text_received),
            ],
            REORDER_GALLERY:         [CallbackQueryHandler(reorder_gallery_chosen, pattern=r"^ro:")],
            REORDER_ORDER:           [MessageHandler(filters.TEXT & ~filters.COMMAND, reorder_order_received)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel), CommandHandler("start", _conv_start)],
        name="local_conv",
        persistent=True,
        allow_reentry=True,
        conversation_timeout=1800,
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("galleries", cmd_galleries))
    app.add_handler(conv)
    app.add_error_handler(lambda u, c: logger.error("Error: %s", c.error, exc_info=c.error))

    print("Bot running — press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
