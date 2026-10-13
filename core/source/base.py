from __future__ import annotations

from pathlib import Path
from typing import Protocol


class VideoSource(Protocol):
    def fetch(self, url: str, out_dir: Path) -> Path:
        """Download the video at `url` into `out_dir` and return its local path."""
        ...
