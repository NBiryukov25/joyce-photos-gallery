#!/usr/bin/env python3
"""
Telegram bot: send a photo → saves to assets/<gallery>/ → updates gallery HTML → commits & pushes.

Required env vars:
  TELEGRAM_BOT_TOKEN       — from @BotFather
  TELEGRAM_ALLOWED_USER_ID — (optional) your Telegram user ID to restrict access

Run:
  python3 telegram_bot.py
"""

import os
import re
import logging
import subprocess
from pathlib import Path

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

REPO_DIR = Path(__file__).parent.resolve()
ASSETS_DIR = REPO_DIR / "assets"
GALLERIES_DIR = REPO_DIR / "galleries"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")

CHOOSING_GALLERY, NAMING_GALLERY, ADDING_CAPTION = range(3)

# Galleries whose photos live in a top-level page rather than galleries/<name>.html
SPECIAL_GALLERY_PAGES: dict[str, Path] = {
    "Joyce-and-Friends": REPO_DIR / "friends.html",
}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# file helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {"videos", "audio", "Gallery_photos"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _existing_galleries() -> list[str]:
    if not ASSETS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in ASSETS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in _SKIP_DIRS
    )


def _next_sequential_filename(gallery_dir: Path) -> str:
    existing = sorted(p for p in gallery_dir.iterdir() if p.suffix.lower() in _IMAGE_EXTS)
    return f"photo-{len(existing) + 1:02d}.jpg"


def _safe_js(value: str) -> str:
    """Escape single quotes so the value is safe inside a JS single-quoted string."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _insert_into_js_array(text: str, var_name: str, value: str) -> str:
    """Append value as the last item in `var <var_name> = [...];`."""
    pattern = rf"(var {re.escape(var_name)}\s*=\s*\[)([\s\S]*?)(\];)"

    def replacer(m: re.Match) -> str:
        pre, content, post = m.group(1), m.group(2), m.group(3)
        stripped = content.rstrip()
        if stripped and not stripped.endswith(","):
            stripped += ","
        return pre + stripped + f"\n        '{_safe_js(value)}',\n      " + post

    return re.sub(pattern, replacer, text)


def _add_photo_to_gallery_html(html_path: Path, filename: str, caption: str) -> None:
    text = html_path.read_text(encoding="utf-8")
    text = _insert_into_js_array(text, "filenames", filename)
    # Only modify an explicit captions array; leave auto-generated map() patterns alone
    if re.search(r"var captions\s*=\s*\[", text):
        text = _insert_into_js_array(text, "captions", caption)
    html_path.write_text(text, encoding="utf-8")


def _create_gallery_html(gallery: str, filename: str, caption: str) -> None:
    template = (GALLERIES_DIR / "_template-gallery.html").read_text(encoding="utf-8")
    title = gallery.replace("-", " ").title()

    template = template.replace("GALLERY TITLE", title)
    template = template.replace("ASSET-FOLDER-NAME", gallery)

    template = re.sub(
        r"var filenames\s*=\s*\[[\s\S]*?\];",
        f"var filenames = [\n        '{_safe_js(filename)}'\n      ];",
        template,
    )

    if caption:
        template = re.sub(
            r"var captions\s*=[\s\S]*?;",
            f"var captions = [\n        '{_safe_js(caption)}'\n      ];",
            template,
        )

    out = GALLERIES_DIR / f"{gallery.lower()}.html"
    out.write_text(template, encoding="utf-8")
    logger.info("Created %s", out)


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------


def _git_push(gallery: str, filename: str) -> tuple[bool, str]:
    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(list(args), cwd=REPO_DIR, capture_output=True, text=True)

    run("git", "add", "-A")
    commit = run("git", "commit", "-m", f"Add {filename} to {gallery}")
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
        return False, (commit.stderr or commit.stdout).strip()

    push = run("git", "push")
    if push.returncode != 0:
        return False, push.stderr.strip()
    return True, ""


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
        "Send as a file (Document) to preserve full quality.\n\n"
        "/galleries — list existing galleries\n"
        "/cancel    — cancel current operation"
    )


async def cmd_galleries(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    galleries = _existing_galleries()
    if galleries:
        lines = "\n".join(f"• {g}" for g in galleries)
        await update.message.reply_text(f"Galleries:\n{lines}")
    else:
        await update.message.reply_text("No galleries found in assets/.")


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
        context.user_data["use_original_name"] = True
    else:
        context.user_data["file_id"] = update.message.photo[-1].file_id
        context.user_data["use_original_name"] = False

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
    choice = query.data[2:]  # strip "g:" prefix

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
    (ASSETS_DIR / name).mkdir(parents=True, exist_ok=True)
    await update.message.reply_text(f"Gallery: {name}\n\nCaption? (or /skip)")
    return ADDING_CAPTION


async def caption_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = update.message.text.strip()
    return await _finalize(update, context)


async def caption_skipped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caption"] = ""
    return await _finalize(update, context)


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gallery = context.user_data["gallery"]
    caption = context.user_data.get("caption", "")
    file_id = context.user_data["file_id"]
    use_original = context.user_data.get("use_original_name", False)

    status = await update.message.reply_text("Downloading photo...")

    gallery_dir = ASSETS_DIR / gallery
    gallery_dir.mkdir(parents=True, exist_ok=True)

    if use_original:
        original = context.user_data.get("original_name", "photo.jpg")
        dest = gallery_dir / original
        if dest.exists():
            stem, ext = Path(original).stem, Path(original).suffix or ".jpg"
            dest = gallery_dir / f"{stem}-{len(list(gallery_dir.iterdir())) + 1}{ext}"
    else:
        dest = gallery_dir / _next_sequential_filename(gallery_dir)

    tg_file = await context.bot.get_file(file_id)
    await tg_file.download_to_drive(str(dest))
    filename = dest.name

    await status.edit_text(f"Saved {filename}. Updating gallery HTML...")

    gallery_html = SPECIAL_GALLERY_PAGES.get(gallery) or GALLERIES_DIR / f"{gallery.lower()}.html"
    if gallery_html.exists():
        _add_photo_to_gallery_html(gallery_html, filename, caption)
    else:
        _create_gallery_html(gallery, filename, caption)

    await status.edit_text("Committing and pushing to GitHub...")

    ok, err = _git_push(gallery, filename)
    if ok:
        await status.edit_text(
            f"{filename} added to {gallery}.\n\n"
            "GitHub Actions will rebuild the site in the next cycle."
        )
    else:
        await status.edit_text(
            f"Saved and updated HTML, but git push failed:\n\n{err}\n\n"
            "Run `git push` manually to publish."
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
            NAMING_GALLERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, gallery_named)],
            ADDING_CAPTION: [
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
