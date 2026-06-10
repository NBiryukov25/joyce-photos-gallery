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
import os
import re
import logging
import tempfile
from pathlib import Path

import requests
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
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "NBiryukov25/joyce-photos-gallery")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")

CHOOSING_GALLERY, NAMING_GALLERY, ADDING_CAPTION = range(3)

# Galleries that map to a top-level page instead of galleries/<name>.html
SPECIAL_HTML: dict[str, str] = {
    "Joyce-and-Friends": "friends.html",
}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

_GH_API = "https://api.github.com"


def _gh_headers() -> dict:
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def _gh_get_file(rel_path: str) -> tuple[bytes | None, str | None]:
    """Return (content_bytes, sha) or (None, None) if not found."""
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel_path}"
    r = requests.get(url, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)
    if r.status_code == 200:
        data = r.json()
        return base64.b64decode(data["content"]), data["sha"]
    return None, None


def _gh_put_file(rel_path: str, content: bytes, message: str, sha: str | None = None) -> tuple[bool, str]:
    """Create or update a file in the GitHub repo."""
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
    r = requests.put(url, json=body, headers=_gh_headers(), timeout=30)
    if r.status_code in (200, 201):
        return True, ""
    return False, r.json().get("message", f"HTTP {r.status_code}")


def _gh_list_dir(rel_path: str) -> list[dict]:
    """List files in a GitHub directory."""
    url = f"{_GH_API}/repos/{GITHUB_REPO}/contents/{rel_path}"
    r = requests.get(url, headers=_gh_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)
    if r.status_code == 200 and isinstance(r.json(), list):
        return r.json()
    return []


# ---------------------------------------------------------------------------
# gallery helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"videos", "audio", "Gallery_photos"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


_ASSETS_DIR = Path(__file__).parent.resolve() / "assets"


def _existing_galleries() -> list[str]:
    """List gallery folders from local filesystem (fast)."""
    if not _ASSETS_DIR.exists():
        return []
    return sorted(
        d.name for d in _ASSETS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in _SKIP_DIRS
    )


def _next_filename(gallery: str, use_original: bool, original_name: str) -> str:
    if use_original:
        return original_name
    # Use GitHub to count existing photos so numbering is always correct
    files = _gh_list_dir(f"assets/{gallery}")
    images = [f for f in files if Path(f["name"]).suffix.lower() in _IMAGE_EXTS and not f["name"].startswith(".")]
    return f"photo-{len(images) + 1:02d}.jpg"


def _safe_js(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _insert_into_js_array(text: str, var_name: str, value: str) -> str:
    pattern = rf"(var {re.escape(var_name)}\s*=\s*\[)([\s\S]*?)(\];)"

    def replacer(m: re.Match) -> str:
        pre, content, post = m.group(1), m.group(2), m.group(3)
        stripped = content.rstrip()
        if stripped and not stripped.endswith(","):
            stripped += ","
        return pre + stripped + f"\n        '{_safe_js(value)}',\n      " + post

    return re.sub(pattern, replacer, text)


def _updated_gallery_html(current_html: bytes, filename: str, caption: str) -> bytes:
    text = current_html.decode("utf-8")
    text = _insert_into_js_array(text, "filenames", filename)
    if re.search(r"var captions\s*=\s*\[", text):
        text = _insert_into_js_array(text, "captions", caption)
    return text.encode("utf-8")


def _new_gallery_html(template_bytes: bytes, gallery: str, filename: str, caption: str) -> bytes:
    text = template_bytes.decode("utf-8")
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
    if gallery in SPECIAL_HTML:
        return SPECIAL_HTML[gallery]
    return f"galleries/{gallery.lower()}.html"


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
    galleries = _existing_galleries()
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

    galleries = _existing_galleries()

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
    gallery  = context.user_data["gallery"]
    caption  = context.user_data.get("caption", "")
    file_id  = context.user_data["file_id"]
    use_orig = context.user_data.get("use_original", False)
    orig_name = context.user_data.get("original_name", "photo.jpg")

    status = await update.message.reply_text("Downloading photo...")

    # Download from Telegram to a temp file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(str(tmp_path))
    photo_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    filename = await asyncio.to_thread(_next_filename, gallery, use_orig, orig_name)
    photo_rel = f"assets/{gallery}/{filename}"

    await status.edit_text(f"Uploading {filename} to GitHub...")

    # Upload photo
    ok, err = await asyncio.to_thread(_gh_put_file, photo_rel, photo_bytes, f"Add {filename} to {gallery}")
    if not ok:
        await status.edit_text(f"Photo upload failed: {err}")
        return ConversationHandler.END

    await status.edit_text("Updating gallery page...")

    # Update or create the gallery HTML
    html_rel = _html_rel_path(gallery)
    current_html, html_sha = await asyncio.to_thread(_gh_get_file, html_rel)

    if current_html is not None:
        new_html = _updated_gallery_html(current_html, filename, caption)
    else:
        template_bytes, _ = await asyncio.to_thread(_gh_get_file, "galleries/_template-gallery.html")
        if not template_bytes:
            await status.edit_text("Could not find gallery template.")
            return ConversationHandler.END
        new_html = _new_gallery_html(template_bytes, gallery, filename, caption)

    ok, err = await asyncio.to_thread(_gh_put_file, html_rel, new_html, f"Update {gallery} — add {filename}", html_sha)
    if ok:
        await status.edit_text(
            f"{filename} added to {gallery}.\n\n"
            "GitHub Actions will rebuild the site shortly."
        )
    else:
        await status.edit_text(
            f"Photo uploaded but HTML update failed: {err}"
        )

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
