#!/usr/bin/env python3
"""
Transcribe spoken audio from .mp3, .mov, or .mp4 files into verbatim .txt transcripts.

Usage:
    python3 tools/transcribe_video.py <file_or_folder> [options]

Examples:
    python3 tools/transcribe_video.py my_video.mov
    python3 tools/transcribe_video.py ~/Movies --output transcripts/
    python3 tools/transcribe_video.py ~/Movies --model medium --language en

Each input file gets a .txt file with the same name, containing the spoken
words in order, one line per spoken segment.

Setup (one-time):
    pip install -r tools/transcribe_requirements.txt

This runs entirely on your own machine using faster-whisper (a local
speech-recognition model) — no audio is uploaded anywhere and no API key
is required. The first run for a given --model size downloads the model
weights from Hugging Face, so an internet connection is needed then.
"""

import argparse
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".mov", ".mp4"}


def find_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {input_path.suffix}. Expected .mp3, .mov, or .mp4")
        return [input_path]
    if input_path.is_dir():
        files = sorted(
            p for p in input_path.rglob("*")
            if p.suffix.lower() in SUPPORTED_EXTENSIONS and p.is_file()
        )
        if not files:
            raise ValueError(f"No .mp3, .mov, or .mp4 files found in {input_path}")
        return files
    raise FileNotFoundError(f"No such file or folder: {input_path}")


def transcribe_file(model, media_path: Path, output_dir: Path, language: str | None, timestamps: bool) -> Path:
    segments, _info = model.transcribe(
        str(media_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    lines = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if timestamps:
            start = f"{int(segment.start // 60):02d}:{int(segment.start % 60):02d}"
            lines.append(f"[{start}] {text}")
        else:
            lines.append(text)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{media_path.stem}.txt"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Transcribe .mp3/.mov/.mp4 files to verbatim .txt transcripts.")
    parser.add_argument("input", help="Path to a single .mp3/.mov/.mp4 file, or a folder to scan for them")
    parser.add_argument("--output", "-o", default=None, help="Folder to write .txt files to (default: same folder as each source file)")
    parser.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large-v3"], help="Whisper model size (default: small). Larger = more accurate, slower.")
    parser.add_argument("--language", default=None, help="Force a language code (e.g. 'en'). Default: auto-detect.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Run on CPU or GPU (default: cpu)")
    parser.add_argument("--timestamps", action="store_true", help="Prefix each line with a [mm:ss] timestamp")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit(
            "Missing dependency 'faster-whisper'.\n"
            "Install it first:\n"
            "    pip install -r tools/transcribe_requirements.txt"
        )

    input_path = Path(args.input).expanduser().resolve()

    try:
        files = find_input_files(input_path)
    except (ValueError, FileNotFoundError) as e:
        sys.exit(str(e))

    print(f"Loading Whisper model '{args.model}' ({args.device})...")
    compute_type = "int8" if args.device == "cpu" else "float16"
    model = WhisperModel(args.model, device=args.device, compute_type=compute_type)

    for i, media_path in enumerate(files, 1):
        output_dir = Path(args.output).expanduser().resolve() if args.output else media_path.parent
        print(f"[{i}/{len(files)}] Transcribing {media_path.name}...")
        try:
            out_path = transcribe_file(model, media_path, output_dir, args.language, args.timestamps)
            print(f"    -> {out_path}")
        except Exception as e:
            print(f"    ! Failed: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
