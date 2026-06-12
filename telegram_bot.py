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
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "NBiryukov25/joyce-photos-gallery")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")

_repo_owner, _repo_name = GITHUB_REPO.split("/", 1)
GITHUB_PAGES_URL = f"https://{_repo_owner}.github.io/{_repo_name}"

CHOOSING_GALLERY, NAMING_GALLERY, ADDING_CAPTION = range(3)

SPECIAL_HTML: dict[str, str] = {
    "Joyce-and-Friends": "friends.html",
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


# ---------------------------------------------------------------------------
# gallery helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"videos", "audio", "Gallery_photos"}


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


def _make_filename(use_original: bool, original_name: str) -> str:
    if use_original:
        return original_name
    return f"photo-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jpg"


def _safe_js(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


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


def _updated_html(current: bytes, gallery: str, filename: str, caption: str) -> bytes:
    text = current.decode("utf-8")

    if re.search(r"var filenames\s*=\s*\[", text):
        # Slideshow gallery: update JS arrays
        text = _insert_into_js_array(text, "filenames", filename)
        if re.search(r"var captions\s*=\s*\[", text):
            text = _insert_into_js_array(text, "captions", caption)
    elif re.search(r'class="photo-grid"', text):
        # Photo-grid gallery (e.g. friends.html): append a photo-item div
        asset_path = f"assets/{gallery}/{filename}"
        label = _safe_html(caption if caption else filename)
        new_item = (
            f'\n      <div class="photo-item">\n'
            f'        <img src="{asset_path}" alt="{_safe_html(caption or "Photo")}"'
            f' data-caption="{_safe_html(caption)}">\n'
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
        text = re.sub(
            r"var captions\s*=[\s\S]*?;",
            f"var captions = [\n        '{_safe_js(caption)}'\n      ];",
            text,
        )
    return text.encode("utf-8")


def _html_rel_path(gallery: str) -> str:
    return SPECIAL_HTML.get(gallery) or f"galleries/{gallery.lower()}.html"


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
        "Send a photo to add it to a gallery.\n"
        "Send as a file to preserve full quality.\n\n"
        "/galleries — list existing galleries\n"
        "/cancel    — cancel current operation"
    )


async def cmd_galleries(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    galleries = await _existing_galleries()
    if galleries:
        lines = "\n".join(f"• {g}" for g in galleries)
        await update.message.reply_text(f"Galleries:\n{lines}")
    else:
        await update.message.reply_text("No galleries found.")


# ---------------------------------------------------------------------------
# conversation: photo → gallery → caption → done
# ---------------------------------------------------------------------------


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _authorized(update):
        await update.message.reply_text("Not authorized.")
        return ConversationHandler.END

    if update.message.document:
        context.user_data["file_id"] = update.message.document.file_id
        context.user_data["original_name"] = update.message.document.file_name or "photo.jpg"
        context.user_data["use_original"] = True
    else:
        context.user_data["file_id"] = update.message.photo[-1].file_id
        context.user_data["use_original"] = False

    galleries = await _existing_galleries()
    keyboard = [[InlineKeyboardButton(g, callback_data=f"g:{g}")] for g in galleries]
    keyboard.append([InlineKeyboardButton("+ New Gallery", callback_data="g:__new__")])

    await update.message.reply_text(
        "Which gallery?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_GALLERY


async def gallery_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data[2:]

    if choice == "__new__":
        await query.edit_message_text("New gallery name? (e.g. Paris-Summer)")
        return NAMING_GALLERY

    context.user_data["gallery"] = choice
    await query.edit_message_text(f"Adding to {choice}.\n\nCaption? (or /skip)")
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

    status = await update.message.reply_text("Downloading photo...")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    tg_file = await context.bot.get_file(file_id)
    await asyncio.wait_for(tg_file.download_to_drive(str(tmp_path)), timeout=30)
    raw_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    await status.edit_text("Compressing photo...")
    photo_bytes = _compress_photo(raw_bytes)
    kb = len(photo_bytes) // 1024
    logger.info("Compressed photo: %d KB (was %d KB)", kb, len(raw_bytes) // 1024)

    filename  = _make_filename(use_orig, orig_name)
    photo_rel = f"assets/{gallery}/{filename}"

    await status.edit_text(f"Uploading to GitHub ({kb} KB)...")

    ok, err = await _gh_put_file(photo_rel, photo_bytes, f"Add {filename} to {gallery}")
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
    if ok:
        gallery_url = f"{GITHUB_PAGES_URL}/{html_rel}"
        await status.edit_text(
            f"✓ {filename} added to {gallery}.\n\n"
            f"Gallery: {gallery_url}\n\n"
            "(Site rebuilds in ~30 seconds)"
        )
    else:
        await status.edit_text(f"Photo uploaded but page update failed: {err}")

    return ConversationHandler.END


async def cmd_cancel(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_received)],
        states={
            CHOOSING_GALLERY: [CallbackQueryHandler(gallery_chosen, pattern=r"^g:")],
            NAMING_GALLERY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, gallery_named)],
            ADDING_CAPTION:   [
                CommandHandler("skip", caption_skipped),
                MessageHandler(filters.TEXT & ~filters.COMMAND, caption_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("galleries", cmd_galleries))
    app.add_handler(conv)

    logger.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
