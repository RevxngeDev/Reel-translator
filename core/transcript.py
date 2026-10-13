"""The transcript JSON: single source of truth for every job output (D-001, D-015)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Word:
    word: str
    start: float
    end: float


@dataclass
class Segment:
    id: int
    start: float
    end: float
    source_lang: str
    original_text: str
    translated_text: str | None = None
    words: list[Word] = field(default_factory=list)  # timings of original_text words


def save(segments: list[Segment], path: Path) -> None:
    data = [asdict(s) for s in segments]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> list[Segment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = []
    for item in data:
        words = [Word(**w) for w in item.pop("words", [])]
        segments.append(Segment(**item, words=words))
    return segments
