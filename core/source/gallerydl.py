"""MediaSource backed by gallery-dl (D-025): handles Instagram carousels and image
posts, which yt-dlp does not. Runs gallery-dl as a subprocess of the same Python.

Cookies follow D-013 (dedicated secondary account only).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from core.errors import FetchError
from core.source.base import Media


class GalleryDlSource:
    def __init__(self, cookies_file: Path | None = None, cookies_browser: str | None = None) -> None:
        if cookies_file and cookies_browser:
            raise ValueError("Use either cookies_file or cookies_browser, not both")
        self._cookies_file = cookies_file
        self._cookies_browser = cookies_browser

    def command(self, url: str, out_dir: Path) -> list[str]:
        cmd = [
            sys.executable, "-m", "gallery_dl", "-q",
            "--http-timeout", "60",
            "-D", str(out_dir),
            # Zero-padded index keeps the post's order when sorting by name.
            "-f", "{num:>03}.{extension}",
        ]
        if self._cookies_file:
            cmd += ["--cookies", str(self._cookies_file)]
        if self._cookies_browser:
            cmd += ["--cookies-from-browser", self._cookies_browser]
        return cmd + [url]

    def fetch(self, url: str, out_dir: Path) -> Media:
        if self._cookies_file and not self._cookies_file.is_file():
            raise FetchError(f"Cookies file not found: {self._cookies_file}")
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(self.command(url, out_dir), capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise FetchError("gallery-dl timed out") from exc
        media = Media.from_files(sorted(p for p in out_dir.iterdir() if p.is_file()))
        if result.returncode != 0 or media.empty:
            raise FetchError(f"gallery-dl failed ({result.returncode}): {result.stderr.strip()[-300:]}")
        return media
