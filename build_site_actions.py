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

CSS = """
:root { --text-normal:#1a1a1a; --text-muted:#6b6b6b; --background-modifier-border:#d4d4d4; --background-body:#faf9f7; }
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background-color:var(--background-body);color:var(--text-normal);font-family:Georgia,"Times New Roman",serif;padding:3em 2em 5em;max-width:1100px;margin:0 auto;}
.gallery-page-title{font-size:2.2em;font-weight:400;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:0.2em;margin-top:0.5em;}
.gallery-page-subtitle{font-size:0.95em;font-weight:300;letter-spacing:0.18em;text-transform:uppercase;color:var(--text-muted);margin-bottom:2em;}
.gallery-divider{border:none;border-top:1px solid var(--background-modifier-border);margin:1.5em 0 2em 0;}
.gallery-section-label{font-size:0.78em;letter-spacing:0.22em;text-transform:uppercase;color:var(--text-muted);margin-bottom:0.75em;margin-top:2em;padding-bottom:0.4em;border-bottom:1px solid var(--background-modifier-border);}
.gallery-row{display:flex;flex-direction:row;overflow-x:auto;gap:20px;padding:0 0 18px 0;margin-bottom:1.5em;scrollbar-width:thin;scrollbar-color:var(--background-modifier-border) transparent;-webkit-overflow-scrolling:touch;}
.gallery-row::-webkit-scrollbar{height:5px;}.gallery-row::-webkit-scrollbar-track{background:transparent;}.gallery-row::-webkit-scrollbar-thumb{background-color:var(--background-modifier-border);border-radius:3px;}
.gallery-item{flex:0 0 auto;width:240px;display:flex;flex-direction:column;align-items:flex-start;}
@media(max-width:600px){.gallery-item{width:68vw;}}
.gallery-item a{display:block;width:100%;text-decoration:none;border:none;box-shadow:none;}
.gallery-item img{width:100%;height:180px;object-fit:cover;display:block;border-radius:2px;transition:opacity 0.25s ease;box-shadow:0 2px 12px rgba(0,0,0,0.12);}
.gallery-item a:hover img{opacity:0.88;}
.gallery-caption{margin-top:10px;padding:0 2px;width:100%;}
.gallery-caption-title{font-size:0.82em;font-weight:400;letter-spacing:0.03em;margin:0 0 3px 0;line-height:1.3;}
.gallery-caption-meta{font-size:0.72em;font-weight:300;font-style:italic;color:var(--text-muted);margin:0;letter-spacing:0.01em;line-height:1.4;}
.gallery-caption-text{font-size:0.74em;color:var(--text-muted);margin-top:4px;line-height:1.45;font-style:italic;}
.gallery-view-link{display:inline-block;margin-top:5px;font-size:0.68em;letter-spacing:0.14em;text-transform:uppercase;color:var(--text-muted);text-decoration:none;border-bottom:1px solid var(--background-modifier-border);padding-bottom:1px;transition:color 0.2s;}
.gallery-view-link:hover{color:var(--text-normal);border-bottom-color:var(--text-muted);}
"""

PORTFOLIO_CSS = """
:root { --text-normal:#1a1a1a; --text-muted:#6b6b6b; --background-modifier-border:#d4d4d4; --background-body:#faf9f7; }
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background-color:var(--background-body);color:var(--text-normal);font-family:Georgia,"Times New Roman",serif;padding:3em 2em 5em;max-width:1100px;margin:0 auto;}
.back-link{display:inline-block;font-size:0.72em;letter-spacing:0.16em;text-transform:uppercase;color:var(--text-muted);text-decoration:none;border-bottom:1px solid var(--background-modifier-border);padding-bottom:1px;margin-bottom:2.5em;transition:color 0.2s;}
.back-link:hover{color:var(--text-normal);}
.portfolio-title{font-size:2em;font-weight:400;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:0.2em;}
.portfolio-subtitle{font-size:0.88em;font-weight:300;letter-spacing:0.18em;text-transform:uppercase;color:var(--text-muted);margin-bottom:0.6em;}
.portfolio-caption{font-size:0.92em;font-weight:300;line-height:1.8;color:var(--text-muted);max-width:720px;margin-bottom:0.5em;font-style:italic;}
.portfolio-meta{font-size:0.78em;letter-spacing:0.06em;color:var(--text-muted);margin-bottom:2em;}
.portfolio-divider{border:none;border-top:1px solid var(--background-modifier-border);margin:1.5em 0 2.5em 0;}
.photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:28px;}
@media(max-width:600px){.photo-grid{grid-template-columns:1fr;}}
.photo-item{display:flex;flex-direction:column;}
.photo-item img{width:100%;display:block;border-radius:2px;box-shadow:0 2px 14px rgba(0,0,0,0.13);transition:opacity 0.25s ease;object-fit:cover;}
.photo-item img:hover{opacity:0.9;}
.photo-info{margin-top:10px;padding:0 2px;}
.photo-title{font-size:0.82em;font-weight:400;letter-spacing:0.03em;margin-bottom:3px;line-height:1.3;}
.photo-caption{font-size:0.74em;color:var(--text-muted);line-height:1.5;font-style:italic;}
.photo-meta{font-size:0.68em;color:var(--text-muted);margin-top:3px;letter-spacing:0.04em;}
.empty-notice{font-size:0.9em;color:var(--text-muted);font-style:italic;padding:2em 0;}
"""

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

def build_card(g, use_portfolio_link=True):
    title = h(g.get("Gallery Title", "Untitled"))
    meta = h(g.get("Camera Metadata", ""))
    caption = h(g.get("Gallery Caption", ""))
    img_url = g.get("Cover Image URL", "")
    ext_link = g.get("Full Series Link", "") or ""

    # Prefer the generated portfolio page link; fall back to external link
    if use_portfolio_link:
        slug = slugify(g.get("Gallery Title", "gallery"))
        link = f"galleries/{slug}.html"
    elif ext_link:
        link = ext_link
    else:
        link = "#"

    target = '_blank" rel="noopener' if link.startswith("http") else '_self'
    img_tag = (f'<img src="{h(img_url)}" alt="{title}">'
               if img_url else
               '<div style="width:100%;height:180px;background:#e8e8e8;border-radius:2px;"></div>')
    cap_html = f'\n        <p class="gallery-caption-text">{caption}</p>' if caption else ""
    link_html = f'\n        <a class="gallery-view-link" href="{h(link)}" target="{target}">View full series \u2192</a>'
    return (f'\n    <div class="gallery-item">'
            f'<a href="{h(link)}" target="{target}">{img_tag}</a>'
            f'<div class="gallery-caption">'
            f'<p class="gallery-caption-title">{title}</p>'
            f'<p class="gallery-caption-meta">{meta}</p>'
            f'{cap_html}{link_html}'
            f'</div></div>')

def build_html(by_series):
    preferred = ["Series I \u2014 Light & Form","Series II \u2014 Landscapes","Series III \u2014 Portraits","Series IV \u2014 Color Studies"]
    sections, seen = "", set()
    for name in preferred + [s for s in by_series if s not in preferred]:
        if name in seen or name not in by_series:
            continue
        seen.add(name)
        galleries = sorted(by_series[name], key=lambda g: int(g.get("Sort Order") or 999))
        sections += (f'\n  <div class="gallery-section-label">{h(name)}</div>\n'
                     f'  <div class="gallery-row">{"".join(build_card(g) for g in galleries)}\n  </div>\n')
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            f'  <meta charset="UTF-8">\n'
            f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'  <title>Joyce Photos \u00b7 Collection I</title>\n'
            f'  <style>{CSS}\n'
            f'.gallery-intro-headline{{font-size:1.15em;font-weight:400;letter-spacing:0.02em;line-height:1.5;margin:1.5em 0 0.75em 0;color:var(--text-normal);max-width:780px;}}\n'
            f'.gallery-intro-body{{font-size:0.92em;font-weight:300;line-height:1.8;color:var(--text-muted);max-width:780px;margin-bottom:1.5em;font-style:italic;}}\n'
            f'</style>\n</head>\n<body>\n'
            f'  <div class="gallery-page-title">Collection I</div>\n'
            f'  <div class="gallery-page-subtitle">An ongoing archive &nbsp;\u00b7&nbsp; Vol. 1</div>\n'
            f'  <p class="gallery-intro-headline">Discover the Radiance of Sheryl Joyce \u2013 Alluring Filipino Beauty Captured in Timeless Light</p>\n'
            f'  <p class="gallery-intro-body">This exquisite collection unveils Sheryl Joyce \u2013 a vision of tropical elegance and enigmatic grace. Her warm, sun-kissed Filipina features glow against lush landscapes, hinting at private moments of raw, unfiltered desire that lie beneath the surface. From the soft caress of golden hour on her curves to the playful dance of morning light on her silhouette, each image celebrates her magnetic allure and a complexity known only to the few.</p>\n'
            f'  <hr class="gallery-divider">\n'
            f'{sections}\n</body>\n</html>\n')

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
            f'  <title>{title} \u00b7 Joyce Photos</title>\n'
            f'  <style>{PORTFOLIO_CSS}</style>\n'
            f'</head>\n<body>\n'
            f'  <a class="back-link" href="../index.html">\u2190 Back to Collection I</a>\n'
            f'  <div class="portfolio-title">{title}</div>\n'
            f'  <div class="portfolio-subtitle">{series}</div>\n'
            f'  {caption_html}{meta_html}'
            f'<hr class="portfolio-divider">\n'
            f'  {grid_html}\n'
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
        gallery_name = p.get("Gallery", "").strip()
        if gallery_name:
            photos_by_gallery[gallery_name].append(p)

    # --- Build main index.html ---
    by_series = defaultdict(list)
    for g in published:
        by_series[g.get("Series","Uncategorized")].append(g)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_html(by_series))
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
