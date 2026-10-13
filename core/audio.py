"""Audio extraction with ffmpeg: mono 16 kHz FLAC, the format Groq STT expects."""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.errors import AudioExtractionError


def extract_audio(video_path: Path, out_dir: Path) -> Path:
    audio_path = out_dir / f"{video_path.stem}.flac"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video_path),
        "-map", "0:a:0",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "flac",
        str(audio_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise AudioExtractionError("ffmpeg is not installed or not on PATH") from exc
    if result.returncode != 0:
        raise AudioExtractionError(f"ffmpeg failed: {result.stderr.strip()}")
    return audio_path
