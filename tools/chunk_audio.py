#!/usr/bin/env python3
"""
Split the audio from a long .mp3/.mov/.mp4 file into sequential chunks
small enough for cloud transcription APIs (e.g. OpenAI Whisper's 25 MB
upload limit).

Usage:
    python3 tools/chunk_audio.py input.mov
    python3 tools/chunk_audio.py input.mov --output-dir chunks/ --max-mb 24

Each chunk is a low-bitrate mono audio file (plenty for speech
transcription, and far smaller than the source video) named so that
sorting them alphabetically reproduces the original order:

    chunk_000.mp3, chunk_001.mp3, chunk_002.mp3, ...

Feed the chunks to a transcription step in that order, then concatenate
the resulting text to get the full verbatim transcript.

Requires ffmpeg/ffprobe to be installed and on PATH.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".mov", ".mp4"}


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        if __name__ == "__main__":
            sys.exit(
                "ffmpeg/ffprobe not found.\n"
                "Install it first, e.g.:\n"
                "    brew install ffmpeg        (macOS)\n"
                "    sudo apt install ffmpeg    (Linux)"
            )
        raise RuntimeError(
            "ffmpeg/ffprobe not found on this server. "
            "Contact the site admin."
        )


def run_ffmpeg(args: list[str]):
    result = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True)
    if result.returncode != 0:
        if __name__ == "__main__":
            sys.exit(f"ffmpeg failed:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def parse_bitrate(bitrate: str) -> int:
    """Convert a bitrate string like '64k' into bits per second."""
    bitrate = bitrate.strip().lower()
    if bitrate.endswith("k"):
        return int(float(bitrate[:-1]) * 1000)
    if bitrate.endswith("m"):
        return int(float(bitrate[:-1]) * 1_000_000)
    return int(bitrate)


def get_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        if __name__ == "__main__":
            sys.exit(f"ffprobe failed to read duration:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"ffprobe failed to read duration:\n{result.stderr[-2000:]}")
    return float(result.stdout.strip())


def extract_audio(source: Path, dest: Path, bitrate: str):
    """Extract/convert the audio track to a single mono, low-bitrate mp3."""
    run_ffmpeg([
        "-i", str(source),
        "-vn",              # drop video
        "-ac", "1",         # mono
        "-b:a", bitrate,    # low bitrate is plenty for speech
        str(dest),
    ])


def split_into_chunks(audio_path: Path, output_dir: Path, chunk_seconds: int) -> list[Path]:
    pattern = output_dir / "chunk_%03d.mp3"
    run_ffmpeg([
        "-i", str(audio_path),
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-c", "copy",
        "-reset_timestamps", "1",
        str(pattern),
    ])
    return sorted(output_dir.glob("chunk_*.mp3"))


def main():
    parser = argparse.ArgumentParser(description="Split audio from an .mp3/.mov/.mp4 file into sequential chunks under a size limit.")
    parser.add_argument("input", help="Path to a .mp3, .mov, or .mp4 file")
    parser.add_argument("--output-dir", "-o", default=None, help="Folder to write chunks to (default: <input-name>_chunks/ next to the source file)")
    parser.add_argument("--max-mb", type=float, default=24, help="Maximum size per chunk in MB (default: 24, safely under OpenAI's 25 MB limit)")
    parser.add_argument("--bitrate", default="64k", help="Audio bitrate for the extracted track (default: 64k -- plenty for speech, keeps chunks small)")
    args = parser.parse_args()

    check_ffmpeg()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        sys.exit(f"No such file: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        sys.exit(f"Unsupported file type: {input_path.suffix}. Expected .mp3, .mov, or .mp4")

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else input_path.parent / f"{input_path.stem}_chunks"
    output_dir.mkdir(parents=True, exist_ok=True)

    bitrate_bps = parse_bitrate(args.bitrate)
    max_bytes = args.max_mb * 1_000_000
    safety_factor = 0.9  # leaves headroom for container overhead / bitrate variance
    chunk_seconds = int((max_bytes * 8 * safety_factor) / bitrate_bps)
    if chunk_seconds < 30:
        sys.exit("Computed chunk length is too short -- raise --max-mb or lower --bitrate.")

    print(f"Extracting audio from {input_path.name}...")
    tmp_audio = output_dir.parent / f".{input_path.stem}_full.mp3"
    try:
        extract_audio(input_path, tmp_audio, args.bitrate)

        duration = get_duration_seconds(tmp_audio)
        print(f"Audio duration: {duration / 60:.1f} min. Splitting into ~{chunk_seconds // 60}-minute chunks...")

        chunks = split_into_chunks(tmp_audio, output_dir, chunk_seconds)
    finally:
        tmp_audio.unlink(missing_ok=True)

    if not chunks:
        sys.exit("No chunks were produced -- check the source file.")

    print(f"Created {len(chunks)} chunk(s) in {output_dir}:")
    for i, chunk in enumerate(chunks, 1):
        size_mb = chunk.stat().st_size / 1_000_000
        print(f"  [{i}/{len(chunks)}] {chunk.name}  ({size_mb:.1f} MB)")
    print("Feed these to your transcription step in order, then concatenate the results.")


if __name__ == "__main__":
    main()
