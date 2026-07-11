#!/usr/bin/env python3
"""Optimize a gallery's photos into web-friendly WebP.

The sub-galleries currently serve full-size PNG/JPG originals (often
1-2 MB each) as both the grid thumbnails and the lightbox image. This
script produces a single resized WebP per photo — small enough to load
fast, large enough to look sharp full-screen — and reports the savings.

Usage
-----
    python tools/optimize_gallery_images.py assets/Bohemian-Adventures
    python tools/optimize_gallery_images.py assets/Bohemian-Adventures --max 1600 --quality 82

By default WebP files are written next to the originals with the same
stem (``photo.png`` -> ``photo.webp``). Point your gallery's ``filenames``
array at the ``.webp`` names once you're happy with the result; keep or
archive the originals as your master copies.
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required:  python -m pip install Pillow")

SOURCE_EXTS = {".jpg", ".jpeg", ".png"}


def human(n_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024 or unit == "GB":
            return f"{n_bytes:.0f} {unit}" if unit == "B" else f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024


def convert(src: Path, max_dim: int, quality: int, overwrite: bool):
    dst = src.with_suffix(".webp")
    if dst.exists() and not overwrite and dst.stat().st_mtime >= src.stat().st_mtime:
        return None  # already up to date

    with Image.open(src) as im:
        # Respect EXIF orientation, then flatten to RGB for WebP.
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "P", "LA"):
            im = im.convert("RGB")
        im.thumbnail((max_dim, max_dim), Image.LANCZOS)
        im.save(dst, "WEBP", quality=quality, method=6)

    return src.stat().st_size, dst.stat().st_size, dst.name


def main():
    ap = argparse.ArgumentParser(description="Convert a gallery folder to optimized WebP.")
    ap.add_argument("folder", help="Path to the asset folder, e.g. assets/Bohemian-Adventures")
    ap.add_argument("--max", type=int, default=1600, help="Max width/height in px (default 1600)")
    ap.add_argument("--quality", type=int, default=82, help="WebP quality 0-100 (default 82)")
    ap.add_argument("--overwrite", action="store_true", help="Rebuild even if a WebP already exists")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    sources = sorted(p for p in folder.iterdir()
                     if p.suffix.lower() in SOURCE_EXTS and p.is_file())
    if not sources:
        sys.exit(f"No JPG/PNG images found in {folder}")

    total_in = total_out = 0
    converted = skipped = 0
    print(f"Optimizing {len(sources)} image(s) in {folder}  "
          f"(max {args.max}px, q{args.quality})\n")

    for src in sources:
        result = convert(src, args.max, args.quality, args.overwrite)
        if result is None:
            skipped += 1
            print(f"  skip   {src.name}  (webp already current)")
            continue
        in_b, out_b, name = result
        total_in += in_b
        total_out += out_b
        converted += 1
        pct = (1 - out_b / in_b) * 100 if in_b else 0
        print(f"  ok     {src.name:<32} {human(in_b):>9} -> {human(out_b):>9}  (-{pct:.0f}%)  {name}")

    print()
    if converted:
        pct = (1 - total_out / total_in) * 100 if total_in else 0
        print(f"Converted {converted} file(s): {human(total_in)} -> {human(total_out)}  (-{pct:.0f}% total)")
    if skipped:
        print(f"Skipped {skipped} already-current file(s). Use --overwrite to force.")


if __name__ == "__main__":
    main()
