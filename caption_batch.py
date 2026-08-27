#!/usr/bin/env python3
"""
Batch caption generator for gallery HTML files.

Usage:
    python caption_batch.py [gallery-name]        # one gallery
    python caption_batch.py                        # all galleries

Requirements (one of):
    - Ollama running locally: https://ollama.com
      Pull a vision model first:  ollama pull llama3.2-vision
    - xAI API key:  export XAI_API_KEY=xai-...
    - OpenRouter key: export OPENROUTER_API_KEY=sk-or-...

Run from the root of your cloned repo.
"""

import base64
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_URL   = os.environ.get("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2-vision")
XAI_API_KEY  = os.environ.get("XAI_API_KEY",  "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

GALLERIES_DIR = Path("galleries")
ASSETS_DIR    = Path("assets")

DEFAULT_TONE = (
    "erotic, intimate, playful — short (1-3 sentences), "
    "written as internal monologue or poetic description, "
    "no generic phrases like 'beautiful' or 'stunning'"
)

# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def get_slides(html: str) -> list[dict]:
    m = re.search(r"var slides\s*=\s*\[([\s\S]*?)\];", html)
    if not m:
        return []
    results = []
    for obj in re.finditer(r"\{([^{}]+)\}", m.group(1)):
        t = obj.group(1)
        fn = re.search(r"filename:\s*'([^']+)'", t)
        if not fn:
            continue
        cap = re.search(r"caption:\s*'((?:[^'\\]|\\.)*)'", t)
        results.append({
            "filename": fn.group(1),
            "caption":  cap.group(1).replace("\\'", "'") if cap else "",
            "raw":      obj.group(0),
        })
    return results


def set_slide_caption(html: str, filename: str, new_caption: str) -> str:
    escaped = new_caption.replace("\\", "\\\\").replace("'", "\\'")

    def replacer(m: re.Match) -> str:
        inner = m.group(1)
        fn = re.search(r"filename:\s*'([^']+)'", inner)
        if not fn or fn.group(1) != filename:
            return m.group(0)
        # replace or insert caption field
        if re.search(r"caption:\s*'", inner):
            inner = re.sub(r"caption:\s*'(?:[^'\\]|\\.)*'", f"caption: '{escaped}'", inner)
        else:
            inner = inner.rstrip(", ") + f", caption: '{escaped}'"
        return "{" + inner + "}"

    return re.sub(r"\{([^{}]+)\}", replacer, html)


# ---------------------------------------------------------------------------
# AI backends
# ---------------------------------------------------------------------------

def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


def caption_via_ollama(image_path: Path, tone: str) -> str:
    import urllib.request, json
    # moondream works best with a direct question; other models prefer instruction form
    is_moondream = "moondream" in OLLAMA_MODEL.lower()
    if is_moondream:
        prompt = (
            f"Describe what is happening in this photo in 1-3 sentences. "
            f"Focus on the mood, the person, and the scene. Be {tone}."
        )
    else:
        prompt = (
            f"Write a caption for this photo. Tone: {tone}. "
            "Return ONLY the caption text, nothing else."
        )
    data = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "images": [_b64(image_path)],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    text = result.get("response", "").strip()
    if not text:
        raise RuntimeError("Model returned empty response — try a different prompt or model.")
    return text


def caption_via_xai(image_path: Path, tone: str) -> str:
    import urllib.request, json
    prompt = (
        f"Write a caption for this photo. Tone: {tone}. "
        "Return ONLY the caption text, nothing else."
    )
    payload = {
        "model": "grok-2-vision-latest",
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(image_path)}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def caption_via_openrouter(image_path: Path, tone: str) -> str:
    import urllib.request, json
    prompt = (
        f"Write a caption for this photo. Tone: {tone}. "
        "Return ONLY the caption text, nothing else."
    )
    payload = {
        "model": "meta-llama/llama-3.2-11b-vision-instruct:free",
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(image_path)}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/NBiryukov25/joyce-photos-gallery",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def generate_caption(image_path: Path, tone: str) -> str:
    errors = []

    # 1. Try Ollama (local, fully uncensored)
    try:
        return caption_via_ollama(image_path, tone)
    except Exception as e:
        errors.append(f"Ollama: {e}")

    # 2. Try xAI Grok (permissive)
    if XAI_API_KEY:
        try:
            return caption_via_xai(image_path, tone)
        except Exception as e:
            errors.append(f"xAI: {e}")

    # 3. Try OpenRouter
    if OPENROUTER_API_KEY:
        try:
            return caption_via_openrouter(image_path, tone)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    raise RuntimeError("All backends failed:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def process_gallery(html_path: Path, tone: str, skip_existing: bool) -> int:
    html = html_path.read_text(encoding="utf-8")
    slides = get_slides(html)
    if not slides:
        print(f"  No var slides found in {html_path.name} — skipping.")
        return 0

    # find the assets folder for this gallery
    gallery_name = None
    m = re.search(r"BASE\s*=\s*['\"]\.\.\/assets\/([^'\"]+)['\"]", html)
    if m:
        gallery_name = m.group(1)
    if not gallery_name:
        # try to infer from asset paths in slides
        fn_sample = slides[0]["filename"]
        for d in ASSETS_DIR.iterdir():
            if d.is_dir() and (d / fn_sample).exists():
                gallery_name = d.name
                break
    if not gallery_name:
        print(f"  Could not find assets folder for {html_path.name} — skipping.")
        return 0

    assets = ASSETS_DIR / gallery_name
    changed = 0

    for i, slide in enumerate(slides):
        filename = slide["filename"]
        existing = slide["caption"]

        if skip_existing and existing:
            continue

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in ("mp4", "mov", "webm"):
            print(f"\n[{i+1}/{len(slides)}] {filename}  (video — skip)")
            continue

        image_path = assets / filename
        if not image_path.exists():
            print(f"\n[{i+1}/{len(slides)}] {filename}  ⚠ file not found — skip")
            continue

        print(f"\n[{i+1}/{len(slides)}] {filename}")
        if existing:
            print(f"  Current: {existing!r}")

        # Generate
        print("  Generating…", end="", flush=True)
        try:
            suggested = generate_caption(image_path, tone)
            print(f"\r  Suggested: {suggested}")
        except Exception as e:
            print(f"\r  ERROR: {e}")
            suggested = ""

        # Interactive review
        while True:
            if suggested:
                choice = input("  [u]se / [e]dit / [s]kip / [q]uit? ").strip().lower()
            else:
                choice = input("  [e]nter caption / [s]kip / [q]uit? ").strip().lower()

            if choice == "q":
                if changed:
                    html_path.write_text(html, encoding="utf-8")
                    print(f"\n  Saved {changed} caption(s) to {html_path.name}")
                print("  Quitting.")
                sys.exit(0)

            if choice == "s":
                break

            if choice == "u" and suggested:
                html = set_slide_caption(html, filename, suggested)
                changed += 1
                print(f"  ✓ saved")
                break

            if choice == "e":
                new_cap = input("  Caption: ").strip()
                if new_cap:
                    html = set_slide_caption(html, filename, new_cap)
                    changed += 1
                    print(f"  ✓ saved")
                break

            if choice == "t":
                tone = input("  New tone: ").strip() or tone
                print("  Regenerating…", end="", flush=True)
                try:
                    suggested = generate_caption(image_path, tone)
                    print(f"\r  Suggested: {suggested}")
                except Exception as e:
                    print(f"\r  ERROR: {e}")
                    suggested = ""

    if changed:
        html_path.write_text(html, encoding="utf-8")
        print(f"\n  ✓ Saved {changed} caption(s) to {html_path.name}")
    else:
        print(f"\n  No changes to {html_path.name}")

    return changed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Determine which galleries to process
    if len(sys.argv) > 1:
        name = sys.argv[1]
        # Accept gallery name (e.g. "Petite-Traitor") or filename
        candidates = [
            GALLERIES_DIR / f"{name}.html",
            GALLERIES_DIR / f"{name.lower()}.html",
            GALLERIES_DIR / f"petit-traitor.html",
        ]
        html_files = [p for p in candidates if p.exists()]
        if not html_files:
            print(f"Gallery '{name}' not found. Files in galleries/:")
            for f in sorted(GALLERIES_DIR.glob("*.html")):
                print(f"  {f.stem}")
            sys.exit(1)
        html_files = [html_files[0]]
    else:
        html_files = sorted(GALLERIES_DIR.glob("*.html"))
        # Skip index-like files
        html_files = [f for f in html_files if not f.stem.startswith("_")]

    print("=== Gallery Caption Batch Tool ===")
    print()
    print("Backends available:")
    try:
        import urllib.request
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        print(f"  ✓ Ollama at {OLLAMA_URL}  (model: {OLLAMA_MODEL})")
    except Exception:
        print(f"  ✗ Ollama not reachable at {OLLAMA_URL}")
        print(f"      → Install from https://ollama.com then run:")
        print(f"        ollama pull {OLLAMA_MODEL}")
    if XAI_API_KEY:
        print(f"  ✓ xAI Grok  (XAI_API_KEY set)")
    if OPENROUTER_API_KEY:
        print(f"  ✓ OpenRouter  (OPENROUTER_API_KEY set)")
    if not XAI_API_KEY and not OPENROUTER_API_KEY:
        print(f"  — xAI / OpenRouter not configured (set XAI_API_KEY or OPENROUTER_API_KEY)")
    print()

    skip_existing = input("Skip slides that already have captions? [Y/n]: ").strip().lower() != "n"
    tone = input(f"Caption tone [{DEFAULT_TONE[:60]}…]\n(press Enter to use default): ").strip()
    if not tone:
        tone = DEFAULT_TONE
    print()

    total_changed = 0
    for html_path in html_files:
        print(f"\n── {html_path.name} ──")
        total_changed += process_gallery(html_path, tone, skip_existing)

    print(f"\n=== Done. {total_changed} caption(s) written. ===")
    if total_changed:
        print("Review the changes, then:")
        print("  git add galleries/")
        print("  git commit -m 'Add captions'")
        print("  git push")


if __name__ == "__main__":
    main()
