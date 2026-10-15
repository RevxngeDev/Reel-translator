"""Helpers shared by the video and image paths of the pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from core import SUPPORTED_LANGS
from core.errors import SameLanguageError, UnsupportedLanguageError
from core.transcript import Segment
from core.translate.base import Translator


@dataclass
class TextPair:
    original: str
    translated: str


def check_languages(source_lang: str, target_lang: str) -> None:
    if source_lang not in SUPPORTED_LANGS:
        raise UnsupportedLanguageError(source_lang)
    if source_lang == target_lang:
        raise SameLanguageError(f"The content is already in {target_lang}")


def main_language(languages: list[str]) -> str:
    """Most frequent non-empty language; "" if none."""
    counts = Counter(lang for lang in languages if lang)
    return counts.most_common(1)[0][0] if counts else ""


def translate_texts(
    texts: list[str], source_lang: str, target_lang: str, translator: Translator
) -> tuple[list[TextPair], int]:
    """Translate plain texts through the segment translator (ids 1:1 enforced there)."""
    if not texts:
        return [], 0
    segments = [Segment(id=i, start=0.0, end=0.0, source_lang=source_lang, original_text=t)
                for i, t in enumerate(texts)]
    result = translator.translate(segments, source_lang, target_lang)
    return [TextPair(s.original_text, result.translations[s.id]) for s in segments], result.tokens
