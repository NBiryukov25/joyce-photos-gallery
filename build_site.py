#!/usr/bin/env python3
"""
Joyce Photos — Airtable → Website Pipeline
============================================
Reads gallery data from Airtable and regenerates index.html.
Run this script whenever you want to publish updates from Airtable.

Usage:
    python3 build_site.py

Requirements:
    pip install pyairtable
"""

import os
import sys
import json
from collections import defaultdict

try:
    from pyairtable import Api
except ImportError:
    os.system("pip install pyairtable -q")
    from pyairtable import Api

# ── Configuration ────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
BASE_ID        = "appwI079rOz0IKLa7"
GALLERIES_TABLE = "tblWskDpoLczJb0OA"
PHOTOS_TABLE    = "tblhQAUQve8fGgd7p"
OUTPUT_FILE     = os.path.join(os.path.dirname(__file__), "index.html")
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --text-normal: #1a1a1a;
  --text-muted: #6b6b6b;
  --background-modifier-border: #d4d4d4;
  --background-body: #faf9f7;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--background-body);
  color: var(--text-normal);
  font-family: Georgia, "Times New Roman", serif;
  padding: 3em 2em 5em;
  max-width: 1100px;
  margin: 0 auto;
}
.gallery-page-title {
  font-size: 2.2em; font-weight: 400; letter-spacing: 0.08em;
  text-transform: uppercase; margin-bottom: 0.2em; margin-top: 0.5em;
}
.gallery-page-subtitle {
  font-size: 0.95em; font-weight: 300; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--text-muted);
  margin-bottom: 2em;
}
.gallery-divider {
  border: none; border-top: 1px solid var(--background-modifier-border);
  margin: 1.5em 0 2em 0;
}
.gallery-section-label {
  font-size: 0.78em; letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: 0.75em; margin-top: 2em;
  padding-bottom: 0.4em;
  border-bottom: 1px solid var(--background-modifier-border);
}
.gallery-section-caption {
  font-size: 0.82em; font-style: italic; color: var(--text-muted);
  margin-bottom: 1em; margin-top: -0.3em; line-height: 1.5;
}
.gallery-row {
  display: flex; flex-direction: row; overflow-x: auto;
  gap: 20px; padding: 0 0 18px 0; margin-bottom: 1.5em;
  scrollbar-width: thin;
  scrollbar-color: var(--background-modifier-border) transparent;
  -webkit-overflow-scrolling: touch;
}
.gallery-row::-webkit-scrollbar { height: 5px; }
.gallery-row::-webkit-scrollbar-track { background: transparent; }
.gallery-row::-webkit-scrollbar-thumb {
  background-color: var(--background-modifier-border); border-radius: 3px;
}
.gallery-item {
  flex: 0 0 auto; width: 240px;
  display: flex; flex-direction: column; align-items: flex-start;
}
@media (max-width: 600px) { .gallery-item { width: 68vw; } }
.gallery-item a {
  display: block; width: 100%; text-decoration: none;
  border: none; box-shadow: none;
}
.gallery-item img {
  width: 100%; height: 180px; object-fit: cover; display: block;
  border-radius: 2px; transition: opacity 0.25s ease;
  box-shadow: 0 2px 12px rgba(0,0,0,0.12);
}
.gallery-item a:hover img { opacity: 0.88; }
.gallery-caption { margin-top: 10px; padding: 0 2px; width: 100%; }
.gallery-caption-title {
  font-size: 0.82em; font-weight: 400; letter-spacing: 0.03em;
  margin: 0 0 3px 0; line-height: 1.3;
}
.gallery-caption-meta {
  font-size: 0.72em; font-weight: 300; font-style: italic;
  color: var(--text-muted); margin: 0; letter-spacing: 0.01em; line-height: 1.4;
}
.gallery-caption-text {
  font-size: 0.74em; color: var(--text-muted); margin-top: 4px;
  line-height: 1.45; font-style: italic;
}
.gallery-view-link {
  display: inline-block; margin-top: 5px; font-size: 0.68em;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--text-muted); text-decoration: none;
  border-bottom: 1px solid var(--background-modifier-border);
  padding-bottom: 1px; transition: color 0.2s;
}
.gallery-view-link:hover {
  color: var(--text-normal);
  border-bottom-color: var(--text-muted);
}
"""

def html_escape(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def build_gallery_card(gallery):
    f = gallery["fields"]
    title      = html_escape(f.get("Gallery Title", "Untitled"))
    meta       = html_escape(f.get("Camera Metadata", ""))
    caption    = html_escape(f.get("Gallery Caption", ""))
    img_url    = f.get("Cover Image URL", "")
    link       = f.get("Full Series Link", "") or "#"

    img_tag = f'<img src="{html_escape(img_url)}" alt="{title}">' if img_url else \
              f'<div style="width:100%;height:180px;background:#e8e8e8;border-radius:2px;"></div>'

    caption_text_html = f'\n        <p class="gallery-caption-text">{caption}</p>' if caption else ""
    view_link_html = f'\n        <a class="gallery-view-link" href="{html_escape(link)}" target="_blank" rel="noopener">View full series →</a>' if link != "#" else ""

    return f"""
    <div class="gallery-item">
      <a href="{html_escape(link)}" target="_blank" rel="noopener">
        {img_tag}
      </a>
      <div class="gallery-caption">
        <p class="gallery-caption-title">{title}</p>
        <p class="gallery-caption-meta">{meta}</p>{caption_text_html}{view_link_html}
      </div>
    </div>"""

def build_html(galleries_by_series):
    series_order = [
        "Series I — Light & Form",
        "Series II — Landscapes",
        "Series III — Portraits",
        "Series IV — Color Studies",
    ]

    sections_html = ""
    for series_name in series_order:
        galleries = galleries_by_series.get(series_name, [])
        if not galleries:
            continue
        galleries.sort(key=lambda g: g["fields"].get("Sort Order", 999))
        cards = "".join(build_gallery_card(g) for g in galleries)
        sections_html += f"""
  <div class="gallery-section-label">{html_escape(series_name)}</div>
  <div class="gallery-row">{cards}
  </div>
"""

    # Handle any series not in the predefined order
    for series_name, galleries in galleries_by_series.items():
        if series_name not in series_order and galleries:
            galleries.sort(key=lambda g: g["fields"].get("Sort Order", 999))
            cards = "".join(build_gallery_card(g) for g in galleries)
            sections_html += f"""
  <div class="gallery-section-label">{html_escape(series_name)}</div>
  <div class="gallery-row">{cards}
  </div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Joyce Photos — Collection I. An ongoing photographic archive by Joyce.">
  <title>Joyce Photos · Collection I</title>
  <style>{CSS}</style>
</head>
<body>

  <div class="gallery-page-title">Collection I</div>
  <div class="gallery-page-subtitle">An ongoing archive &nbsp;·&nbsp; Vol. 1</div>
  <hr class="gallery-divider">
{sections_html}
</body>
</html>
"""

def main():
    if not AIRTABLE_TOKEN:
        print("ERROR: AIRTABLE_TOKEN environment variable is not set.")
        print("Set it with: export AIRTABLE_TOKEN=your_token_here")
        sys.exit(1)

    print("Connecting to Airtable...")
    api = Api(AIRTABLE_TOKEN)
    galleries_table = api.table(BASE_ID, GALLERIES_TABLE)

    print("Fetching published galleries...")
    all_records = galleries_table.all(formula="{Publish}=1", sort=["Sort Order"])

    if not all_records:
        print("No published galleries found. Check that Publish is checked in Airtable.")
        sys.exit(1)

    print(f"Found {len(all_records)} published galleries.")

    galleries_by_series = defaultdict(list)
    for record in all_records:
        series = record["fields"].get("Series", "Uncategorized")
        galleries_by_series[series].append(record)

    html = build_html(galleries_by_series)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✓ index.html regenerated at: {OUTPUT_FILE}")
    print("\nNext step: commit and push to GitHub to publish the updated site.")
    print("  cd joyce-gallery-site && git add index.html && git commit -m 'Update galleries from Airtable' && git push")

if __name__ == "__main__":
    main()
