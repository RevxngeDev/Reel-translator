"""Default provider wiring, shared by every entry point (CLI, bot, Gepeto skill).

Reads optional settings from the environment (see .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

import groq
import httpx

from core.ocr import GroqVisionReader
from core.source import ChainSource, GalleryDlSource, YtDlpSource
from core.stt import GroqWhisper
from core.translate import FallbackTranslator, GroqLlmTranslator

# D-012
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

# The SDK default (5 s connect, 2 retries) failed on the dev network, whose TLS
# handshakes are sometimes slow (D-018).
GROQ_TIMEOUT = httpx.Timeout(120.0, connect=20.0)
GROQ_MAX_RETRIES = 3


def groq_client() -> groq.Groq:
    return groq.Groq(timeout=GROQ_TIMEOUT, max_retries=GROQ_MAX_RETRIES)


def media_source() -> ChainSource:
    """gallery-dl first (handles image posts), yt-dlp as fallback (D-025). Both use
    the same cookies of the secondary account (D-013)."""
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE") or None
    cookies = {
        "cookies_file": Path(cookies_file) if cookies_file else None,
        "cookies_browser": os.environ.get("YTDLP_COOKIES_BROWSER") or None,
    }
    return ChainSource([GalleryDlSource(**cookies), YtDlpSource(**cookies)])


def ocr_reader() -> GroqVisionReader:
    return GroqVisionReader(client=groq_client())


def speech_to_text() -> GroqWhisper:
    return GroqWhisper(client=groq_client())


def translator() -> FallbackTranslator:
    client = groq_client()
    return FallbackTranslator([
        GroqLlmTranslator(PRIMARY_MODEL, client=client),
        GroqLlmTranslator(FALLBACK_MODEL, client=client),
    ])
