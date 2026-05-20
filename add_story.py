#!/usr/bin/env python3
"""
add_story.py — pipeline for adding a new story to Sheryl Joyce's gallery.

── Usage (from a text file) ────────────────────────────────────────────────
    python3 add_story.py my_story.txt

── Usage (interactive prompts) ─────────────────────────────────────────────
    python3 add_story.py

── Input file format ────────────────────────────────────────────────────────
    title:    The Officer
    tag:      Fiction
    date:     May 2026
    cover_id: 12JHJ4ba43n32sJEwCaD_7It9KLLj4ZRE
    excerpt:  When a routine immigration appointment turns threatening...
    ---
    First paragraph of the story.

    Second paragraph of the story.

    (blank line between every paragraph)
"""

import os
import re
import sys
import subprocess
from datetime import datetime

ROOT         = os.path.dirname(os.path.abspath(__file__))
STORIES_DIR  = os.path.join(ROOT, 'stories')
STORIES_HTML = os.path.join(ROOT, 'stories.html')

# ── HTML templates ────────────────────────────────────────────────────────────

STORY_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{title} — a story by Sheryl Joyce">
  <title>{title} · Sheryl Joyce</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../gallery.css">
</head>
<body>

  <header class="site-header">
    <div class="site-nav">
      <a href="../index.html" class="nav-brand">Sheryl Joyce</a>
      <nav class="nav-links">
        <a href="../index.html" class="nav-link">Galleries</a>
        <a href="../stories.html" class="nav-link active">Stories</a>
      </nav>
    </div>
  </header>

  <div class="story-detail-cover">
    <img class="story-detail-cover-img"
         src="https://drive.google.com/thumbnail?id={cover_id}&sz=w2000"
         alt="{title}">
  </div>

  <div class="story-detail-wrap">
    <a class="back-link" href="../stories.html">← Back to Stories</a>
    <p class="story-detail-tag">{tag}</p>
    <h1 class="story-detail-title">{title}</h1>
    <p class="story-detail-date">{date}</p>
    <hr class="gallery-divider">

    <div class="story-detail-body">

{body}

    </div>
  </div>

</body>
</html>
"""

CARD_TEMPLATE = """\

    <article class="story-card">
      <div class="story-card-img-wrap">
        <img class="story-card-img"
             src="https://drive.google.com/thumbnail?id={cover_id}&sz=w2000"
             alt="{title}">
      </div>
      <p class="story-card-tag">{tag}</p>
      <h2 class="story-card-title">{title}</h2>
      <p class="story-card-date">{date}</p>
      <p class="story-card-excerpt">{excerpt}</p>
      <a class="story-read-link" href="stories/{slug}.html">Read →</a>
    </article>
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text):
    s = text.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s

def body_to_html(raw):
    paras = [p.strip() for p in raw.strip().split('\n\n') if p.strip()]
    return '\n\n'.join(f'      <p>{p}</p>' for p in paras)

def parse_input_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    parts = content.split('---', 1)
    meta_raw = parts[0]
    body_raw = parts[1].strip() if len(parts) > 1 else ''
    meta = {}
    for line in meta_raw.splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            meta[k.strip().lower()] = v.strip()
    return meta, body_raw

def ask(label, default=None):
    hint = f' [{default}]' if default else ''
    val = input(f'  {label}{hint}: ').strip()
    return val if val else (default or '')

def git(cmd):
    r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  git error: {r.stderr.strip()}')
    return r.returncode == 0

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('\n── Add a New Story ──────────────────────────────────────────\n')

    # 1. Collect inputs
    if len(sys.argv) > 1:
        meta, body_raw = parse_input_file(sys.argv[1])
        title    = meta.get('title', '')
        tag      = meta.get('tag', 'Fiction')
        date     = meta.get('date', datetime.now().strftime('%B %Y'))
        cover_id = meta.get('cover_id', '')
        excerpt  = meta.get('excerpt', '')
        slug     = meta.get('slug') or slugify(title)
    else:
        title    = ask('Story title')
        slug     = ask('URL slug (auto)', slugify(title)) or slugify(title)
        tag      = ask('Tag', 'Fiction')
        date     = ask('Date', datetime.now().strftime('%B %Y'))
        cover_id = ask('Cover photo Drive file ID')
        excerpt  = ask('Card excerpt (1–2 sentences)')
        print('\n  Paste story body — blank line between paragraphs.')
        print('  Type END on its own line when finished.\n')
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        body_raw = '\n'.join(lines)

    if not title or not cover_id:
        print('\nERROR: title and cover_id are required.')
        sys.exit(1)

    if not slug:
        slug = slugify(title)

    # 2. Write story HTML
    story_path = os.path.join(STORIES_DIR, f'{slug}.html')
    if os.path.exists(story_path):
        yn = input(f'\n  stories/{slug}.html already exists. Overwrite? [y/N] ').strip().lower()
        if yn != 'y':
            print('  Aborted.')
            sys.exit(0)

    body_html = body_to_html(body_raw) if body_raw.strip() else '      <!-- Add story paragraphs here -->'
    story_html = STORY_TEMPLATE.format(title=title, tag=tag, date=date,
                                        cover_id=cover_id, body=body_html)
    with open(story_path, 'w', encoding='utf-8') as f:
        f.write(story_html)
    print(f'\n  ✓ Created  stories/{slug}.html')

    # 3. Inject card into stories.html (top of the grid)
    card_html = CARD_TEMPLATE.format(title=title, tag=tag, date=date,
                                      cover_id=cover_id, excerpt=excerpt, slug=slug)
    with open(STORIES_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    marker = '<div class="stories-grid">'
    if marker not in html:
        print('  ERROR: could not find .stories-grid in stories.html')
        sys.exit(1)

    html = html.replace(marker, marker + card_html, 1)
    with open(STORIES_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  ✓ Added card to stories.html')

    # 4. Commit and push
    branch = subprocess.check_output('git branch --show-current', shell=True,
                                      cwd=ROOT).decode().strip()
    print(f'\n  Committing to branch: {branch}')
    git(f'git add stories/{slug}.html stories.html')
    git(f'git commit -m "Add story: {title}"')
    pushed = git(f'git push -u origin {branch}')

    print('\n── Done! ────────────────────────────────────────────────────')
    print(f'  Story file : stories/{slug}.html')
    print(f'  Branch     : {branch}')
    if pushed:
        print('  Next step  : open a PR on GitHub and merge to main')
    else:
        print('  Next step  : fix the push error above, then open a PR')
    print()

if __name__ == '__main__':
    main()
