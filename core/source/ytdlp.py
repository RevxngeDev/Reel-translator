"""VideoSource backed by yt-dlp (D-010)."""

from __future__ import annotations

from pathlib import Path

import yt_dlp

from core.errors import FetchError


class YtDlpSource:
    def fetch(self, url: str, out_dir: Path) -> Path:
        opts = {
            "outtmpl": str(out_dir / "video.%(ext)s"),
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
        except yt_dlp.utils.DownloadError as exc:
            raise FetchError(f"Could not fetch video: {exc}") from exc
        if not path.exists():
            raise FetchError(f"Download finished but file is missing: {path}")
        return path
