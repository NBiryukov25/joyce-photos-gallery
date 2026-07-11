from pathlib import Path
import re

root = Path('.')
patterns = [re.compile(name, re.I) for name in ['IMG_5745', 'IMG_5746', 'IMG_5747', 'IMG_5748']]
text_ext = {'.html', '.js', '.css', '.py', '.txt', '.md', '.json'}

matches = []
for p in root.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in text_ext:
        continue
    try:
        text = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    if not any(pattern.search(text) for pattern in patterns):
        continue
    lines = [line.strip() for line in text.splitlines() if any(pattern.search(line) for pattern in patterns)]
    matches.append((p, lines))

print('MATCHING_FILES', len(matches))
for p, lines in matches:
    print('\nFILE:', p.as_posix())
    for line in lines:
        print('  LINE:', line)
