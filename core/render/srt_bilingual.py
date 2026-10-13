"""Bilingual .srt renderer: original on top, translation below (D-002)."""

from __future__ import annotations

from pathlib import Path

from core.transcript import Segment


def _timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def render(segments: list[Segment]) -> str:
    blocks = []
    for n, seg in enumerate(segments, start=1):
        lines = [seg.original_text]
        if seg.translated_text:
            lines.append(seg.translated_text)
        blocks.append(f"{n}\n{_timestamp(seg.start)} --> {_timestamp(seg.end)}\n" + "\n".join(lines) + "\n")
    return "\n".join(blocks)


def write(segments: list[Segment], path: Path) -> None:
    path.write_text(render(segments), encoding="utf-8")
