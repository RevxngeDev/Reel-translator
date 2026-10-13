"""The transcript JSON: single source of truth for every job output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Segment:
    id: int
    start: float
    end: float
    source_lang: str
    original_text: str
    translated_text: str | None = None


def save(segments: list[Segment], path: Path) -> None:
    data = [asdict(s) for s in segments]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> list[Segment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Segment(**item) for item in data]
