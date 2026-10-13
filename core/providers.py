"""Default provider wiring, shared by every entry point (CLI, bot, Gepeto skill).

Reads optional settings from the environment (see .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

from core.source import YtDlpSource
from core.stt import GroqWhisper
from core.translate import FallbackTranslator, GroqLlmTranslator

# D-012
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"


def video_source() -> YtDlpSource:
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE") or None
    return YtDlpSource(
        cookies_file=Path(cookies_file) if cookies_file else None,
        cookies_browser=os.environ.get("YTDLP_COOKIES_BROWSER") or None,
    )


def speech_to_text() -> GroqWhisper:
    return GroqWhisper()


def translator() -> FallbackTranslator:
    return FallbackTranslator([GroqLlmTranslator(PRIMARY_MODEL), GroqLlmTranslator(FALLBACK_MODEL)])
