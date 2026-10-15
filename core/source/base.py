from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Media:
    """The media files of one post, in the post's order."""

    videos: list[Path] = field(default_factory=list)
    images: list[Path] = field(default_factory=list)

    @classmethod
    def from_files(cls, files: list[Path]) -> Media:
        media = cls()
        for f in files:
            ext = f.suffix.lower()
            if ext in VIDEO_EXTS:
                media.videos.append(f)
            elif ext in IMAGE_EXTS:
                media.images.append(f)
        return media

    @property
    def empty(self) -> bool:
        return not self.videos and not self.images


class MediaSource(Protocol):
    def fetch(self, url: str, out_dir: Path) -> Media:
        """Download the post at `url` into `out_dir` and return its media files."""
        ...
