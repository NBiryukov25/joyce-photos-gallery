#!/usr/bin/env python3
"""
Joyce Photos — GitHub Actions Build Script
==========================================
Reads gallery data from public Google Sheets CSV and regenerates:
  - index.html  (main gallery index, unchanged)
  - galleries/  (one HTML page per gallery, powered by the Photos tab)
No API key required — sheet must be shared as "Anyone with the link can view".
"""

import sys
import csv
import os
import re
import urllib.request
from collections import defaultdict
from io import StringIO

SPREADSHEET_ID = "1N8ToEDXnsYKFFRPfYXiqjUqlsPUp5PCMbm0BeZBokTo"
OUTPUT_FILE    = "index.html"
GALLERIES_DIR  = "galleries"

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">'

SITE_NAV = """  <header class="site-header">
    <div class="site-nav">
      <a href="index.html" class="nav-brand">Sheryl Joyce</a>
      <nav class="nav-links">
        <a href="index.html" class="nav-link active">Galleries</a>
        <a href="stories.html" class="nav-link">Stories</a>
      </nav>
    </div>
  </header>"""

GALLERY_NAV = """  <header class="site-header">
    <div class="site-nav">
      <a href="../index.html" class="nav-brand">Sheryl Joyce</a>
      <nav class="nav-links">
        <a href="../index.html" class="nav-link active">Galleries</a>
        <a href="../stories.html" class="nav-link">Stories</a>
      </nav>
    </div>
  </header>"""

def fetch_csv(sheet_name):
    url = (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
           f"/gviz/tq?tqx=out:csv&sheet={urllib.request.quote(sheet_name)}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")

def parse_csv(text):
    reader = csv.DictReader(StringIO(text))
    return [{k: v for k, v in row.items() if k and k.strip()} for row in reader]

def h(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def slugify(title):
    """Convert gallery title to a URL-safe filename."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug or "gallery"

def build_card(g, gallery_has_photos=False):
    title = h(g.get("Gallery Title", "Untitled"))
    meta = h(g.get("Camera Metadata", ""))
    caption = h(g.get("Gallery Caption", ""))
    img_url = g.get("Cover Image URL", "")
    ext_link = (g.get("Full Series Link", "") or "").strip()

    # Priority: 1) External Series Link, 2) Internal portfolio page (if photos exist), 3) no link
    if ext_link:
        link = ext_link
    elif gallery_has_photos:
        slug = slugify(g.get("Gallery Title", "gallery"))
        link = f"galleries/{slug}.html"
    else:
        link = ""

    target = '_blank" rel="noopener' if link.startswith("http") else '_self'
    img_tag = (f'<img src="{h(img_url)}" alt="{title}">'
               if img_url else
               '<div style="width:100%;height:180px;background:#e8e8e8;border-radius:2px;"></div>')
    cap_html = f'\n        <p class="gallery-caption-text">{caption}</p>' if caption else ""
    link_html = (f'\n        <a class="gallery-view-link" href="{h(link)}" target="{target}">View full series \u2192</a>'
                 if link else "")
    img_wrap = (f'<a href="{h(link)}" target="{target}">{img_tag}</a>'
                if link else img_tag)
    return (f'\n    <div class="gallery-item">'
            f'{img_wrap}'
            f'<div class="gallery-caption">'
            f'<p class="gallery-caption-title">{title}</p>'
            f'<p class="gallery-caption-meta">{meta}</p>'
            f'{cap_html}{link_html}'
            f'</div></div>')

def build_html(by_series, photos_by_gallery=None):
    if photos_by_gallery is None:
        photos_by_gallery = {}
    preferred = ["Series I \u2014 Light & Form","Series II \u2014 Landscapes","Series III \u2014 Portraits","Series IV \u2014 Color Studies"]
    sections, seen = "", set()
    for name in preferred + [s for s in by_series if s not in preferred]:
        if name in seen or name not in by_series:
            continue
        seen.add(name)
        galleries = sorted(by_series[name], key=lambda g: int(g.get("Sort Order") or 999))
        cards = "".join(build_card(g, gallery_has_photos=bool(photos_by_gallery.get(g.get("Gallery Title","").strip()))) for g in galleries)
        sections += (f'\n  <div class="gallery-section-label">{h(name)}</div>\n'
                     f'  <div class="gallery-row">{cards}\n  </div>\n')
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'  <meta charset="UTF-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'  <meta name="description" content="Sheryl Joyce \u2014 An ongoing photographic archive. Collection I.">\n'
            f'  <title>Sheryl Joyce</title>\n'
            f'  {FONT_LINK}\n'
            f'  <link rel="stylesheet" href="gallery.css">\n'
            f'</head>\n<body>\n'
            f'{SITE_NAV}\n'
            f'  <section class="hero">\n'
            f'    <p class="hero-overline">Portfolio</p>\n'
            f'    <h1 class="hero-name">Sheryl Joyce</h1>\n'
            f'    <p class="hero-tagline">An ongoing archive &nbsp;\u00b7&nbsp; Vol. 1</p>\n'
            f'    <div class="comp-strip">\n'
            f'      <span class="comp-item"><span class="comp-label">Height</span><span class="comp-value">152 cm</span></span>\n'
            f'      <span class="comp-sep">\u00b7</span>\n'
            f'      <span class="comp-item"><span class="comp-label">Weight</span><span class="comp-value">53 kg</span></span>\n'
            f'      <span class="comp-sep">\u00b7</span>\n'
            f'      <span class="comp-item"><span class="comp-label">Waist</span><span class="comp-value">27 cm</span></span>\n'
            f'      <span class="comp-sep">\u00b7</span>\n'
            f'      <span class="comp-item"><span class="comp-label">Hair</span><span class="comp-value">Black</span></span>\n'
            f'      <span class="comp-sep">\u00b7</span>\n'
            f'      <span class="comp-item"><span class="comp-label">Eyes</span><span class="comp-value">Brown</span></span>\n'
            f'    </div>\n'
            f'  </section>\n'
            f'  <section class="intro-section">\n'
            f'    <p class="intro-headline">Discover the Radiance of Sheryl Joyce \u2013 Alluring Filipino Beauty Captured in Timeless Light</p>\n'
            f'    <p class="intro-body">This exquisite collection unveils Sheryl Joyce \u2013 a vision of tropical elegance and enigmatic grace. Her warm, sun-kissed Filipina features glow against lush landscapes, hinting at private moments of raw, unfiltered desire that lie beneath the surface. From the soft caress of golden hour on her curves to the playful dance of morning light on her silhouette, each image celebrates her magnetic allure and a complexity known only to the few.</p>\n'
            f'  </section>\n'
            f'  <hr class="gallery-divider">\n'
            f'{sections}'
            f'\n  <div class="gallery-section-label">Series III — On Location</div>\n'
            f'  <div class="gallery-row">\n'
            f'    <div class="gallery-item">\n'
            f'      <a href="galleries/a-quiet-distance.html">\n'
            f'        <img src="https://drive.google.com/thumbnail?id=1zkFKOiXoUh_qz-rEwYkvfSM4Dc3FApS_&sz=w2000" alt="A Quiet Distance">\n'
            f'      </a>\n'
            f'      <div class="gallery-caption">\n'
            f'        <p class="gallery-caption-title">A Quiet Distance</p>\n'
            f'        <p class="gallery-caption-meta">Digital, 2024 · Boston, MA</p>\n'
            f'        <p class="gallery-caption-text">She is in the city but not of it — a Filipina woman navigating Boston’s brownstone streets with quiet grace, emotional distance, and a beauty that keeps its own counsel.</p>\n'
            f'        <a class="gallery-view-link" href="galleries/a-quiet-distance.html">View full series →</a>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'  </div>\n'
            f'\n</body>\n</html>\n')

def build_portfolio_page(gallery, photos):
    """Generate an individual gallery portfolio HTML page."""
    title = h(gallery.get("Gallery Title", "Untitled"))
    series = h(gallery.get("Series", ""))
    meta = h(gallery.get("Camera Metadata", ""))
    caption = h(gallery.get("Gallery Caption", ""))

    # Sort photos by Sort Order
    photos_sorted = sorted(photos, key=lambda p: int(p.get("Sort Order") or 999))

    if photos_sorted:
        photo_items = ""
        for p in photos_sorted:
            p_title = h(p.get("Photo Title", ""))
            p_caption = h(p.get("Photo Caption", ""))
            p_meta = h(p.get("Camera Metadata", ""))
            p_img = p.get("Image URL", "")
            img_tag = (f'<img src="{h(p_img)}" alt="{p_title}">'
                       if p_img else
                       '<div style="width:100%;height:260px;background:#e8e8e8;border-radius:2px;"></div>')
            title_html = f'<p class="photo-title">{p_title}</p>' if p_title else ""
            cap_html = f'<p class="photo-caption">{p_caption}</p>' if p_caption else ""
            meta_html = f'<p class="photo-meta">{p_meta}</p>' if p_meta else ""
            info = f'<div class="photo-info">{title_html}{cap_html}{meta_html}</div>' if (p_title or p_caption or p_meta) else ""
            photo_items += f'<div class="photo-item">{img_tag}{info}</div>\n'
        grid_html = f'<div class="photo-grid">\n{photo_items}</div>'
    else:
        grid_html = '<p class="empty-notice">Photos coming soon — check back after the next update.</p>'

    caption_html = f'<p class="portfolio-caption">{caption}</p>\n  ' if caption else ""
    meta_html = f'<p class="portfolio-meta">{meta}</p>\n  ' if meta else ""

    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'  <meta charset="UTF-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'  <title>{title} \u00b7 Sheryl Joyce</title>\n'
            f'  {FONT_LINK}\n'
            f'  <link rel="stylesheet" href="../gallery.css">\n'
            f'  <link rel="stylesheet" href="../lightbox.css">\n'
            f'</head>\n<body>\n'
            f'{GALLERY_NAV}\n'
            f'  <a class="back-link" href="../index.html">\u2190 Back to Galleries</a>\n'
            f'  <div class="portfolio-title">{title}</div>\n'
            f'  <div class="portfolio-subtitle">{series}</div>\n'
            f'  {caption_html}{meta_html}'
            f'<hr class="portfolio-divider">\n'
            f'  {grid_html}\n'
            f'  <script src="../lightbox.js"></script>\n'
            f'</body>\n</html>\n')

def main():
    print("Fetching gallery data from Google Sheets...")

    # --- Galleries tab ---
    galleries_csv = fetch_csv("Galleries")
    galleries = parse_csv(galleries_csv)
    published = [g for g in galleries if g.get("Publish","").strip().upper() in ("TRUE","YES","1")]
    print(f"Found {len(published)} published galleries.")

    # --- Photos tab ---
    print("Fetching photos data from Google Sheets...")
    try:
        photos_csv = fetch_csv("Photos")
        photos_all = parse_csv(photos_csv)
        published_photos = [p for p in photos_all if p.get("Publish","").strip().upper() in ("TRUE","YES","1")]
        print(f"Found {len(published_photos)} published photos.")
    except Exception as e:
        print(f"Warning: Could not fetch Photos tab: {e}")
        published_photos = []

    # Group photos by gallery title
    photos_by_gallery = defaultdict(list)
    for p in published_photos:
        gallery_name = (p.get("Gallery", "") or p.get("Gallery (match Gallery Title exactly)", "")).strip()
        if gallery_name:
            photos_by_gallery[gallery_name].append(p)

    # --- Build main index.html ---
    by_series = defaultdict(list)
    for g in published:
        by_series[g.get("Series","Uncategorized")].append(g)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_html(by_series, photos_by_gallery=photos_by_gallery))
    print(f"Written: {OUTPUT_FILE}")

    # --- Build individual gallery pages ---
    os.makedirs(GALLERIES_DIR, exist_ok=True)
    for g in published:
        slug = slugify(g.get("Gallery Title", "gallery"))
        gallery_photos = photos_by_gallery.get(g.get("Gallery Title","").strip(), [])
        page_html = build_portfolio_page(g, gallery_photos)
        out_path = os.path.join(GALLERIES_DIR, f"{slug}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"Written: {out_path} ({len(gallery_photos)} photos)")

    print("Done!")

if __name__ == "__main__":
    main()
