"""ImageTextReader backed by Groq vision (D-023, D-024).

Per Groq docs read 2026-10-13: `qwen/qwen3.8-27b` is the only vision model; JSON
mode; `reasoning_effort="none"` supported. Observed on the free tier: output tokens
are capped at 1,000/min for this model and requests are rejected up front when
`max_completion_tokens` exceeds it, so the caps below stay under that limit.
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

import groq

from core.errors import OcrError
from core.ocr import grid
from core.ocr.base import ImageText

DEFAULT_MODEL = "qwen/qwen3.8-27b"
MAX_TOKENS_SINGLE = 400
MAX_TOKENS_GRID = 900

_PROMPT = (
    "Extract all readable text from this image exactly as written, in reading order. "
    "Group lines that belong to the same sentence or option into one block; do not repeat text. "
    "Ignore logos, watermarks, usernames, app or brand names and interface elements "
    "(buttons, search bars, 'download the app' banners): keep only the post's own content. "
    "Return JSON: {\"language\": ISO-639-1 code of the main language or \"none\", "
    "\"blocks\": [text blocks]}."
)
_PREFIX = re.compile(r"^\s*\[(\d+)\]\s*(.*)$", re.DOTALL)


def _normalize_lang(value: object) -> str:
    v = str(value or "").strip().lower()
    return "" if v in ("", "none", "null") else v


def split_blocks(blocks: list[str], n: int) -> list[list[str]]:
    """Assign "[k] text" blocks to slides; unprefixed blocks follow the last slide seen."""
    if n == 1:
        return [[b.strip() for b in blocks if b.strip()]]
    out: list[list[str]] = [[] for _ in range(n)]
    current = 0
    for block in blocks:
        m = _PREFIX.match(block)
        if m:
            k = int(m.group(1)) - 1
            current = k if 0 <= k < n else current
            block = m.group(2)
        if block.strip():
            out[current].append(block.strip())
    return out


class GroqVisionReader:
    def __init__(self, client: groq.Groq | None = None, model: str = DEFAULT_MODEL) -> None:
        self._client = client or groq.Groq()
        self._model = model

    def read(self, images: list[Path]) -> list[ImageText]:
        results: list[ImageText] = []
        for i in range(0, len(images), grid.MAX_PER_GRID):
            results.extend(self._read_group(images[i : i + grid.MAX_PER_GRID]))
        return results

    def _read_group(self, paths: list[Path]) -> list[ImageText]:
        n = len(paths)
        buf = io.BytesIO()
        grid.pack(paths).save(buf, format="JPEG", quality=85)
        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": _PROMPT + grid.describe(n)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]}],
                response_format={"type": "json_object"},
                reasoning_effort="none",
                temperature=0.1,
                max_completion_tokens=MAX_TOKENS_SINGLE if n == 1 else MAX_TOKENS_GRID,
            )
        except groq.APIError as exc:
            raise OcrError(f"Groq OCR failed: {exc}") from exc
        try:
            data = json.loads(resp.choices[0].message.content or "")
            blocks = [str(b) for b in data.get("blocks") or []]
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            raise OcrError(f"Groq OCR returned malformed JSON: {exc}") from exc
        language = _normalize_lang(data.get("language"))
        return [ImageText(language if slide else "", slide) for slide in split_blocks(blocks, n)]
