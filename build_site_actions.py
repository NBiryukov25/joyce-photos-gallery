#!/usr/bin/env python3
"""
Joyce Photos — GitHub Actions Build Script
==========================================
Reads gallery data from public Google Sheets CSV and regenerates index.html.
No API key required — sheet must be shared as "Anyone with the link can view".
"""

import sys
import csv
import urllib.request
from collections import defaultdict
from io import StringIO

SPREADSHEET_ID = "1N8ToEDXnsYKFFRPfYXiqjUqlsPUp5PCMbm0BeZBokTo"
OUTPUT_FILE    = "index.html"

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

def build_card(g):
    title, meta, caption = h(g.get("Gallery Title","Untitled")), h(g.get("Camera Metadata","")), h(g.get("Gallery Caption",""))
    img_url, link = g.get("Cover Image URL",""), g.get("Full Series Link","") or "#"
    img_tag = f'<img src="{h(img_url)}" alt="{title}">' if img_url else '<div style="width:100%;height:180px;background:#e8e8e8;border-radius:2px;"></div>'
    cap_html = f'\n        <p class="gallery-caption-text">{caption}</p>' if caption else ""
    link_html = (f'\n        <a class="gallery-view-link" href="{h(link)}" target="_blank" rel="noopener">View full series \u2192</a>') if link != "#" else ""
    return f'\n    <div class="gallery-item"><a href="{h(link)}" target="_blank" rel="noopener">{img_tag}</a><div class="gallery-caption"><p class="gallery-caption-title">{title}</p><p class="gallery-caption-meta">{meta}</p>{cap_html}{link_html}</div></div>'

def build_html(by_series):
    preferred = ["Series I \u2014 Light & Form","Series II \u2014 Landscapes","Series III \u2014 Portraits","Series IV \u2014 Color Studies"]
    sections, seen = "", set()
    for name in preferred + [s for s in by_series if s not in preferred]:
        if name in seen or name not in by_series: continue
        seen.add(name)
        galleries = sorted(by_series[name], key=lambda g: int(g.get("Sort Order") or 999))
        sections += f'\n  <div class="gallery-section-label">{h(name)}</div>\n  <div class="gallery-row">{"".join(build_card(g) for g in galleries)}\n  </div>\n'
    return f'<!DOCTYPE html>\n<html lang="en">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>Joyce Photos \u00b7 Collection I</title>\n  <style>{CSS}\n.gallery-intro-headline{{font-size:1.15em;font-weight:400;letter-spacing:0.02em;line-height:1.5;margin:1.5em 0 0.75em 0;color:var(--text-normal);max-width:780px;}}\n.gallery-intro-body{{font-size:0.92em;font-weight:300;line-height:1.8;color:var(--text-muted);max-width:780px;margin-bottom:1.5em;font-style:italic;}}\n</style>\n</head>\n<body>\n  <div class="gallery-page-title">Collection I</div>\n  <div class="gallery-page-subtitle">An ongoing archive &nbsp;\u00b7&nbsp; Vol. 1</div>\n  <p class="gallery-intro-headline">Discover the Radiance of Sheryl Joyce \u2013 Alluring Filipino Beauty Captured in Timeless Light</p>\n  <p class="gallery-intro-body">This exquisite collection unveils Sheryl Joyce \u2013 a vision of tropical elegance and enigmatic grace. Her warm, sun-kissed Filipina features glow against lush landscapes, hinting at private moments of raw, unfiltered desire that lie beneath the surface. From the soft caress of golden hour on her curves to the playful dance of morning light on her silhouette, each image celebrates her magnetic allure and a complexity known only to the few.</p>\n  <hr class="gallery-divider">\n{sections}\n</body>\n</html>\n'

def main():
    print("Fetching gallery data from Google Sheets...")
    csv_text = fetch_csv("Galleries")
    galleries = parse_csv(csv_text)
    published = [g for g in galleries if g.get("Publish","").strip().upper() in ("TRUE","YES","1")]
    print(f"Found {len(published)} published galleries.")
    by_series = defaultdict(list)
    for g in published:
        by_series[g.get("Series","Uncategorized")].append(g)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_html(by_series))
    print(f"Done! {OUTPUT_FILE} written.")

if __name__ == "__main__":
    main()
