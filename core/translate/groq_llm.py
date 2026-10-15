"""Translator backed by a Groq-hosted LLM (D-005, D-012).

Parameters per Groq docs read on 2026-10-13: strict json_schema structured output
(GPT-OSS models), reasoning_effort, instructions in the user message only.
"""

from __future__ import annotations

import json

import groq

from core.errors import TranslationError
from core.transcript import Segment
from core.translate.base import TranslationResult, check_ids

LANG_NAMES = {"es": "Spanish", "en": "English", "ru": "Russian"}

_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}

_PROMPT = """Translate the text segments of a short social-media post (video subtitles or text shown in images) from {src} to {tgt}.
The audience is a language learner (A2-B2) who will read the original and the translation side by side.

Rules:
- Return exactly one output segment per input segment, with the same id, in the same order.
- Never merge, split, drop or add segments. If a segment is a fragment, translate the fragment.
- Use the surrounding segments as context, but keep each translation inside its own segment.
- Translate naturally and faithfully; keep slang meaning, do not explain it.

Input segments (JSON):
{segments}"""


class GroqLlmTranslator:
    def __init__(
        self,
        model: str,
        client: groq.Groq | None = None,
        batch_size: int = 40,
        reasoning_effort: str = "low",
    ) -> None:
        self._client = client or groq.Groq()
        self._model = model
        self._batch_size = batch_size
        self._reasoning_effort = reasoning_effort

    def translate(self, segments: list[Segment], source_lang: str, target_lang: str) -> TranslationResult:
        translations: dict[int, str] = {}
        tokens = 0
        for i in range(0, len(segments), self._batch_size):
            batch = segments[i : i + self._batch_size]
            batch_translations, batch_tokens = self._translate_batch(batch, source_lang, target_lang)
            translations.update(batch_translations)
            tokens += batch_tokens
        return TranslationResult(translations=translations, tokens=tokens, model=self._model)

    def _translate_batch(self, batch: list[Segment], source_lang: str, target_lang: str) -> tuple[dict[int, str], int]:
        payload = json.dumps([{"id": s.id, "text": s.original_text} for s in batch], ensure_ascii=False)
        prompt = _PROMPT.format(src=LANG_NAMES[source_lang], tgt=LANG_NAMES[target_lang], segments=payload)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "translation", "strict": True, "schema": _SCHEMA},
                },
                reasoning_effort=self._reasoning_effort,
                temperature=0.5,
            )
        except groq.APIError as exc:
            raise TranslationError(f"{self._model}: {exc}") from exc

        try:
            items = json.loads(resp.choices[0].message.content or "")["segments"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise TranslationError(f"{self._model}: malformed response: {exc}") from exc

        check_ids([s.id for s in batch], [item["id"] for item in items])
        tokens = resp.usage.total_tokens if resp.usage else 0
        return {item["id"]: item["text"].strip() for item in items}, tokens
