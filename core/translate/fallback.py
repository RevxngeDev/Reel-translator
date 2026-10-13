"""Tries translators in order. Falls through on provider failures only.

An id mismatch is not a provider failure: it fails the job immediately, so the
invariant violation is never hidden by a retry on another provider.
"""

from __future__ import annotations

from core.errors import TranslationError, TranslationMismatchError
from core.transcript import Segment
from core.translate.base import TranslationResult, Translator


class FallbackTranslator:
    def __init__(self, providers: list[Translator]) -> None:
        if not providers:
            raise ValueError("FallbackTranslator needs at least one provider")
        self._providers = providers

    def translate(self, segments: list[Segment], source_lang: str, target_lang: str) -> TranslationResult:
        errors: list[str] = []
        for provider in self._providers:
            try:
                return provider.translate(segments, source_lang, target_lang)
            except TranslationMismatchError:
                raise
            except TranslationError as exc:
                errors.append(str(exc))
        raise TranslationError("All translation providers failed: " + " | ".join(errors))
