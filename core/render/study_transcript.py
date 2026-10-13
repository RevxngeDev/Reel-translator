"""Study transcript: each original sentence followed by its translation."""

from __future__ import annotations

from pathlib import Path

from core.transcript import Segment


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02}:{s:02}"


def render(segments: list[Segment], source_lang: str, target_lang: str) -> str:
    lines = [f"Transcript ({source_lang} → {target_lang})", ""]
    for seg in segments:
        lines.append(f"[{_clock(seg.start)}] {seg.original_text}")
        lines.append(f"        {seg.translated_text or ''}")
        lines.append("")
    return "\n".join(lines)


def write(segments: list[Segment], source_lang: str, target_lang: str, path: Path) -> None:
    path.write_text(render(segments, source_lang, target_lang), encoding="utf-8")
