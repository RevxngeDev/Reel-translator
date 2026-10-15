"""Tries media sources in order; each gets its own subdirectory so a failed attempt
never leaves files that the next one could pick up.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.errors import FetchError
from core.source.base import Media, MediaSource

log = logging.getLogger(__name__)


class ChainSource:
    def __init__(self, sources: list[MediaSource]) -> None:
        if not sources:
            raise ValueError("ChainSource needs at least one source")
        self._sources = sources

    def fetch(self, url: str, out_dir: Path) -> Media:
        errors: list[str] = []
        for n, source in enumerate(self._sources):
            try:
                return source.fetch(url, out_dir / f"src{n}")
            except FetchError as exc:
                log.info("source %s failed: %s", type(source).__name__, exc)
                errors.append(f"{type(source).__name__}: {exc}")
        raise FetchError("All sources failed: " + " | ".join(errors))
