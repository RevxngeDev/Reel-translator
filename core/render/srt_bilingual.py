"""Bilingual .srt renderer: original on top, translation below (D-002)."""

from __future__ import annotations

from pathlib import Path

from core.render.layout import Cue


def _timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def render(cues: list[Cue]) -> str:
    blocks = []
    for n, cue in enumerate(cues, start=1):
        lines = cue.original + cue.translation
        blocks.append(f"{n}\n{_timestamp(cue.start)} --> {_timestamp(cue.end)}\n" + "\n".join(lines) + "\n")
    return "\n".join(blocks)


def write(cues: list[Cue], path: Path) -> None:
    path.write_text(render(cues), encoding="utf-8")
