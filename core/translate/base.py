from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.errors import TranslationMismatchError
from core.transcript import Segment


@dataclass
class TranslationResult:
    translations: dict[int, str]  # segment id -> translated text
    tokens: int  # total LLM tokens consumed (prompt + completion)
    model: str


class Translator(Protocol):
    def translate(self, segments: list[Segment], source_lang: str, target_lang: str) -> TranslationResult: ...


def check_ids(expected: list[int], received: list[int]) -> None:
    """Enforce the 1:1 id invariant. No repair: any difference fails the job."""
    if expected != received:
        raise TranslationMismatchError(
            f"Translator returned ids {received}, expected {expected}"
        )
