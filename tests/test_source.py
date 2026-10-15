from pathlib import Path

import pytest

from core.errors import FetchError
from core.source import ChainSource, GalleryDlSource, Media, YtDlpSource


def test_anonymous_by_default(tmp_path):
    opts = YtDlpSource().options(tmp_path)
    assert "cookiefile" not in opts and "cookiesfrombrowser" not in opts


def test_cookies_file_option(tmp_path):
    opts = YtDlpSource(cookies_file=Path("c.txt")).options(tmp_path)
    assert opts["cookiefile"] == "c.txt"


def test_cookies_browser_option(tmp_path):
    opts = YtDlpSource(cookies_browser="firefox").options(tmp_path)
    assert opts["cookiesfrombrowser"] == ("firefox",)


def test_both_cookie_sources_rejected():
    with pytest.raises(ValueError):
        YtDlpSource(cookies_file=Path("c.txt"), cookies_browser="firefox")


def test_missing_cookies_file_fails_before_network(tmp_path):
    with pytest.raises(FetchError, match="Cookies file not found"):
        YtDlpSource(cookies_file=tmp_path / "nope.txt").fetch("https://example.invalid", tmp_path)
    with pytest.raises(FetchError, match="Cookies file not found"):
        GalleryDlSource(cookies_file=tmp_path / "nope.txt").fetch("https://example.invalid", tmp_path)


def test_gallery_dl_command_orders_files_and_passes_cookies(tmp_path):
    cmd = GalleryDlSource(cookies_browser="firefox").command("https://x/p/1", tmp_path)
    assert cmd[-1] == "https://x/p/1"
    assert cmd[cmd.index("-f") + 1] == "{num:>03}.{extension}"
    assert cmd[cmd.index("--cookies-from-browser") + 1] == "firefox"
    assert "--cookies" not in cmd


def test_media_from_files_splits_videos_and_images_in_order():
    files = [Path("001.jpg"), Path("002.mp4"), Path("003.PNG"), Path("004.json")]
    media = Media.from_files(files)
    assert media.images == [Path("001.jpg"), Path("003.PNG")] and media.videos == [Path("002.mp4")]
    assert Media().empty and not media.empty


class _Stub:
    def __init__(self, result=None):
        self.result, self.dirs = result, []

    def fetch(self, url, out_dir):
        self.dirs.append(out_dir)
        if self.result is None:
            raise FetchError("unsupported")
        return self.result


def test_chain_falls_back_in_separate_dirs(tmp_path):
    first, second = _Stub(), _Stub(Media(videos=[Path("v.mp4")]))
    media = ChainSource([first, second]).fetch("u", tmp_path)
    assert media.videos == [Path("v.mp4")]
    assert first.dirs[0] != second.dirs[0]


def test_chain_reports_all_failures(tmp_path):
    with pytest.raises(FetchError, match="All sources failed"):
        ChainSource([_Stub(), _Stub()]).fetch("u", tmp_path)
