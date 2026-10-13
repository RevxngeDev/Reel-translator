"""VideoSource backed by yt-dlp (D-010).

Optional authenticated fetch (D-013): cookies of a dedicated secondary account,
either from a Netscape cookies.txt file or read directly from a local browser.
"""

from __future__ import annotations

from pathlib import Path

import yt_dlp

from core.errors import FetchError


class YtDlpSource:
    def __init__(self, cookies_file: Path | None = None, cookies_browser: str | None = None) -> None:
        if cookies_file and cookies_browser:
            raise ValueError("Use either cookies_file or cookies_browser, not both")
        self._cookies_file = cookies_file
        self._cookies_browser = cookies_browser

    def options(self, out_dir: Path) -> dict:
        opts = {
            "outtmpl": str(out_dir / "video.%(ext)s"),
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "noprogress": True,
            # Instagram sometimes answers the video-info request slowly; the
            # default timeout failed on a real reel where 60 s succeeded.
            "socket_timeout": 60,
            "no_warnings": True,
        }
        if self._cookies_file:
            opts["cookiefile"] = str(self._cookies_file)
        if self._cookies_browser:
            opts["cookiesfrombrowser"] = (self._cookies_browser,)
        return opts

    def fetch(self, url: str, out_dir: Path) -> Path:
        if self._cookies_file and not self._cookies_file.is_file():
            raise FetchError(f"Cookies file not found: {self._cookies_file}")
        try:
            with yt_dlp.YoutubeDL(self.options(out_dir)) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
        except yt_dlp.utils.DownloadError as exc:
            raise FetchError(f"Could not fetch video: {exc}") from exc
        if not path.exists():
            raise FetchError(f"Download finished but file is missing: {path}")
        return path
