#!/usr/bin/env python3
"""
add_popup.py — generate a "Featuring" popup and insert it into the Ultra page.

A popup is the same component as the existing "Opening our Doors" one: a modal
slideshow (with the slow Ken-Burns zoom), progress bar, auto-generated dots,
a title and a caption/story. Multiple popups can coexist; od-popup.js shows
them one at a time (first auto-opens, closing it reveals the next).

USAGE
  python tools/add_popup.py --title "TITLE" --photos <dir | file ...> \
         [--message "text" | --message-file FILE] [options]

EXAMPLES
  # All images in a folder, caption inline:
  python tools/add_popup.py \
      --title "A Quiet Evening" \
      --photos assets/Quiet-Evening \
      --message "First paragraph.\n\nSecond paragraph with **emphasis**."

  # Specific photos + caption from a file:
  python tools/add_popup.py \
      --title "Suite 2308" \
      --photos assets/Suite/a.jpg assets/Suite/b.jpg \
      --message-file caption.txt

OPTIONS
  --title         Heading shown at the top of the popup. (required)
  --photos        One folder (all images used, natural-sorted) OR an explicit
                  list of image files. (required)
  --message       Caption/story text. Blank lines start new paragraphs.
                  Markdown-style **bold** and *italic* are converted to HTML.
  --message-file  Read the caption/story from a UTF-8 text file instead.
  --interval      Autoplay speed in milliseconds (default 8000).
  --no-auto       Don't auto-open this popup (open it via JS / a trigger).
  --id            Custom slug used to identify the popup (default: from title).
  --replace       If a popup with the same id already exists, replace it.
  --target        HTML file to insert into (default: joyce-ultra.html).

The caption text is provided by you; this script only formats and inserts it.
"""
import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parent.parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MARKER = "<!-- ultra-popup-insert -->"
ENGINE_TAG = '<script src="od-popup.js"></script>'


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "popup"


def collect_photos(paths):
    files = []
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            path = (REPO / p).resolve() if not path.exists() else path.resolve()
        if path.is_dir():
            found = [f for f in path.iterdir()
                     if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
            files.extend(sorted(found, key=lambda f: natural_key(f.name)))
        elif path.is_file():
            files.append(path)
        else:
            sys.exit(f"error: photo path not found: {p}")
    if not files:
        sys.exit("error: no images found in the given --photos paths")
    return files


def rel_src(photo_abs, target_dir):
    """Path to the photo relative to the target HTML file, URL-encoded."""
    rel = Path(photo_abs).resolve().relative_to(REPO)
    # relative to the target's directory
    import os
    rel_to_target = os.path.relpath((REPO / rel).resolve(), target_dir)
    return quote(rel_to_target.replace("\\", "/"), safe="/")


def md_inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text


def build_message(text):
    if not text:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    body = "\n".join(f"        <p>{md_inline(p)}</p>" for p in paras)
    return f'      <div class="od-message">\n{body}\n      </div>\n'


def build_popup(slug, title, photos, target_dir, message_html, interval, auto):
    alt = html.escape(title, quote=True)
    title_h = html.escape(title, quote=False)
    auto_attr = ' data-od-auto="false"' if not auto else ""

    slides = []
    for i, ph in enumerate(photos):
        active = " active" if i == 0 else ""
        src = rel_src(ph, target_dir)
        slides.append(
            f'        <div class="od-slide{active}">'
            f'<img loading="lazy" decoding="async" src="{src}" alt="{alt}"></div>'
        )
    slides_html = "\n".join(slides)

    return (
        f"  <!-- od-popup:{slug} START -->\n"
        f'  <div class="od-overlay od-hidden" id="od-{slug}" data-od-popup '
        f'data-od-interval="{interval}"{auto_attr}>\n'
        f'    <div class="od-modal">\n'
        f'      <button class="od-close" data-od-close aria-label="Close">✕</button>\n\n'
        f'      <div class="od-header">\n'
        f'        <h2 class="od-title">{title_h}</h2>\n'
        f'        <hr class="od-rule">\n'
        f'      </div>\n\n'
        f'      <div class="od-slides-wrap">\n{slides_html}\n      </div>\n'
        f'      <div class="od-progress"><div class="od-bar"></div></div>\n'
        f'      <div class="od-dots"></div>\n\n'
        f"{message_html}"
        f'      <div class="od-footer">\n'
        f'        <button class="od-enter" data-od-close>Enter</button>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f"  <!-- od-popup:{slug} END -->\n"
    )


def main():
    ap = argparse.ArgumentParser(description="Insert a Featuring popup into the Ultra page.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--photos", required=True, nargs="+")
    ap.add_argument("--message")
    ap.add_argument("--message-file")
    ap.add_argument("--interval", type=int, default=8000)
    ap.add_argument("--no-auto", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--target", default="joyce-ultra.html")
    args = ap.parse_args()

    target = (REPO / args.target).resolve()
    if not target.exists():
        sys.exit(f"error: target not found: {target}")
    target_dir = target.parent

    message = args.message
    if args.message_file:
        message = Path(args.message_file).read_text(encoding="utf-8")
    if message:
        message = message.replace("\\n", "\n")  # allow literal \n in --message

    photos = collect_photos(args.photos)
    slug = slugify(args.id or args.title)
    message_html = build_message(message)
    block = build_popup(slug, args.title, photos, target_dir,
                        message_html, args.interval, not args.no_auto)

    text = target.read_text(encoding="utf-8")

    # sanity: popup CSS must be available on the page
    if ".od-overlay" not in text and "od-modal" not in text:
        print("WARNING: the target page has no .od-* popup CSS. Copy the styles "
              "from joyce-ultra.html (or popup-template.html) into it, or the "
              "popup will be unstyled.")

    start_c = f"<!-- od-popup:{slug} START -->"
    end_c = f"<!-- od-popup:{slug} END -->"
    exists = start_c in text

    if exists and not args.replace:
        sys.exit(f"error: a popup with id 'od-{slug}' already exists. "
                 f"Use --replace to overwrite it, or pass a different --id.")

    if exists and args.replace:
        pattern = r"[ \t]*" + re.escape(start_c) + r".*?" + re.escape(end_c) + r"[ \t]*\n"
        text = re.sub(pattern, block, text, count=1, flags=re.DOTALL)
        action = "replaced"
    else:
        if MARKER not in text:
            # ensure marker + engine exist just before </body>
            inject = f"\n  {MARKER}\n\n  {ENGINE_TAG}\n"
            text = text.replace("</body>", inject + "</body>", 1)
        # consume the marker's own indentation so the block isn't double-indented
        pattern = r"[ \t]*" + re.escape(MARKER)
        text = re.sub(pattern, block.rstrip("\n") + "\n  " + MARKER, text, count=1)
        action = "added"

    if ENGINE_TAG not in text:
        text = text.replace("</body>", f"  {ENGINE_TAG}\n</body>", 1)

    target.write_text(text, encoding="utf-8")
    print(f"{action} popup 'od-{slug}' ({len(photos)} photos) in {target.name}")
    print(f"  title:    {args.title}")
    print(f"  auto-open: {'no' if args.no_auto else 'yes'} · interval: {args.interval}ms")


if __name__ == "__main__":
    main()
