#!/usr/bin/env python3
"""Download Google Drive images referenced in the site into assets/from-drive/
and rewrite all HTML references to local relative paths."""
import re, sys, urllib.request, concurrent.futures
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "from-drive"
OUT.mkdir(parents=True, exist_ok=True)

html_files = [p for p in ROOT.rglob("*.html") if "archive" not in p.parts]

# image-bearing drive URL forms (NOT file/d/.../view document links)
ID_RE = re.compile(
    r"(?:drive\.google\.com/thumbnail\?id=|"
    r"drive\.google\.com/uc\?export=[a-z]+&(?:amp;)?id=|"
    r"lh3\.googleusercontent\.com/d/)([A-Za-z0-9_-]{20,})"
)
FULL_RE = re.compile(
    r"https://(?:drive\.google\.com/thumbnail\?id=|"
    r"drive\.google\.com/uc\?export=[a-z]+&(?:amp;)?id=|"
    r"lh3\.googleusercontent\.com/d/)([A-Za-z0-9_-]{20,})"
    r"(?:=[ws]\d+|&(?:amp;)?sz=w\d+)?"
)

ids = set()
for f in html_files:
    for m in ID_RE.finditer(f.read_text(encoding="utf-8", errors="ignore")):
        ids.add(m.group(1))
print(f"{len(ids)} unique image ids referenced")

EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

def download(id_):
    url = f"https://lh3.googleusercontent.com/d/{id_}=w2048"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            ct = r.headers.get("Content-Type", "").split(";")[0].strip()
            data = r.read()
    except Exception as e:
        return id_, None, f"http error: {e}"
    ext = EXT.get(ct)
    if not ext:
        return id_, None, f"not an image ({ct})"
    (OUT / f"{id_}.{ext}").write_bytes(data)
    return id_, f"{id_}.{ext}", None

mapping, fails = {}, []
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for id_, name, err in ex.map(download, sorted(ids)):
        if name:
            mapping[id_] = name
        else:
            fails.append((id_, err))
print(f"downloaded {len(mapping)}, failed {len(fails)}")
for id_, err in fails:
    print(f"  FAIL {id_}: {err}")

def rewrite(f):
    rel_depth = len(f.relative_to(ROOT).parts) - 1
    prefix = "../" * rel_depth + "assets/from-drive/"
    txt = f.read_text(encoding="utf-8", errors="ignore")
    def repl(m):
        name = mapping.get(m.group(1))
        return prefix + name if name else m.group(0)
    new = FULL_RE.sub(repl, txt)
    if new != txt:
        f.write_text(new, encoding="utf-8")
        return True
    return False

changed = [f.relative_to(ROOT).as_posix() for f in html_files if rewrite(f)]
print(f"rewrote {len(changed)} html files")
