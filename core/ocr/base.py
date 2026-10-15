from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ImageText:
    language: str  # ISO-639-1 code of the main text language, "" if no text
    blocks: list[str] = field(default_factory=list)  # text blocks in reading order


class ImageTextReader(Protocol):
    def read(self, images: list[Path]) -> list[ImageText]:
        """Return the text of each image, one ImageText per image, same order."""
        ...
