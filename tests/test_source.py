from pathlib import Path

import pytest

from core.errors import FetchError
from core.source import YtDlpSource


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
