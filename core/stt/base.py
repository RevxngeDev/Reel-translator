from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Word:
    word: str
    start: float
    end: float


@dataclass
class SttSegment:
    start: float
    end: float
    text: str


@dataclass
class SttResult:
    language: str  # ISO-639-1 code, normalized by the provider
    segments: list[SttSegment]
    duration: float  # seconds of audio processed
    words: list[Word] = field(default_factory=list)


class SpeechToText(Protocol):
    def transcribe(self, audio_path: Path) -> SttResult: ...
