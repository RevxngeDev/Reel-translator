"""SpeechToText backed by Groq Whisper (D-004).

Parameters per Groq docs read on 2026-10-13: response_format=verbose_json,
timestamp_granularities=["word", "segment"].
"""

from __future__ import annotations

from pathlib import Path

import groq

from core.errors import SpeechToTextError
from core.stt.base import SttResult, SttSegment, Word

DEFAULT_MODEL = "whisper-large-v3-turbo"

# Whisper may report the language as a name rather than an ISO code.
_LANG_NAMES = {"spanish": "es", "english": "en", "russian": "ru"}


def normalize_language(value: str | None) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    return _LANG_NAMES.get(v, v)


class GroqWhisper:
    def __init__(self, client: groq.Groq | None = None, model: str = DEFAULT_MODEL) -> None:
        self._client = client or groq.Groq()
        self._model = model

    def transcribe(self, audio_path: Path) -> SttResult:
        try:
            with audio_path.open("rb") as f:
                resp = self._client.audio.transcriptions.create(
                    file=(audio_path.name, f.read()),
                    model=self._model,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"],
                    temperature=0.0,
                )
        except groq.APIError as exc:
            raise SpeechToTextError(f"Groq STT failed: {exc}") from exc
        return parse_verbose_json(resp.model_dump())


def parse_verbose_json(data: dict) -> SttResult:
    segments = [
        SttSegment(start=float(s["start"]), end=float(s["end"]), text=s["text"].strip())
        for s in data.get("segments") or []
        if s.get("text", "").strip()
    ]
    words = [
        Word(word=w["word"], start=float(w["start"]), end=float(w["end"]))
        for w in data.get("words") or []
    ]
    duration = data.get("duration")
    if duration is None:
        duration = segments[-1].end if segments else 0.0
    return SttResult(
        language=normalize_language(data.get("language")),
        segments=segments,
        duration=float(duration),
        words=words,
    )
