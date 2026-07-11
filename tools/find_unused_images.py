import re
from pathlib import Path

root = Path('.')
image_ext = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.tif', '.tiff', '.bmp'}

all_images = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in image_ext and ('assets' in p.parts or 'assets_clean' in p.parts)]
used = set()

for page in list(root.glob('galleries/*.html')) + list(root.glob('*.html')):
    text = page.read_text(encoding='utf-8', errors='ignore')

    for m in re.finditer(r'src=["\']([^"\']+)["\']', text):
        src = m.group(1)
        candidate = None
        if src.startswith('https://raw.githubusercontent.com/'):
            parts = src.split('/main/', 1)
            if len(parts) == 2:
                candidate = (root / parts[1]).resolve()
        elif not (src.startswith('http://') or src.startswith('https://')):
            candidate = (page.parent / src).resolve()
        if candidate and candidate.exists() and candidate.suffix.lower() in image_ext:
            used.add(candidate)

    for m in re.finditer(r'var\s+filenames\s*=\s*\[(.*?)\];', text, re.S):
        block = m.group(1)
        for name in re.findall(r'["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp|avif|tif|tiff|bmp))["\']', block, re.I):
            page_name = page.stem.lower()
            album_hint = None
            if page_name == 'softness-in-surrender':
                album_hint = 'Softness-in-Surrender'
            elif page_name == 'sheryl-joyce-sweetheart':
                album_hint = 'Sheryl-Joyce-Sweetheart'
            elif page_name == 'stashed-companion':
                album_hint = 'Stashed-companion'
            elif page_name == 'domestic-helper':
                album_hint = 'domestic-helper'
            elif page_name == 'bohemian-adventures':
                album_hint = 'Bohemian-Adventures'
            elif page_name == 'capri':
                album_hint = 'Capri'
            if album_hint:
                candidate = (root / 'assets' / album_hint / name).resolve()
                if candidate.exists():
                    used.add(candidate)
                    continue
            candidate = next((p for p in all_images if p.name.lower() == name.lower()), None)
            if candidate:
                used.add(candidate)

for p in root.rglob('*.html'):
    text = p.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'(?:(?:\.\./)?assets(?:/[^"\'\s)]+\.(?:jpg|jpeg|png|gif|webp|avif|tif|tiff|bmp)))', text, re.I):
        candidate = (p.parent / m.group(0)).resolve()
        if candidate.exists():
            used.add(candidate)

unused = [p for p in all_images if p.resolve() not in used]

print('TOTAL_IMAGE_FILES', len(all_images))
print('USED_IMAGE_FILES', len(used))
print('UNUSED_IMAGE_FILES', len(unused))
for p in unused:
    print(p.as_posix())
