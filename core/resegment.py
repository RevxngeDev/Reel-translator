"""Splits long STT segments into subtitle-sized segments using word timestamps (D-016).

Runs before translation, so every final segment is translated as a unit and the
translator still receives and returns ids 1:1.
"""

from __future__ import annotations

from core.stt.base import SttResult, SttSegment
from core.transcript import Segment, Word

MAX_SEGMENT_CHARS = 64  # leaves room for a longer translation in 2 x 42 chars

_STRONG_PUNCT = (".", "?", "!", "…")
_WEAK_PUNCT = (",", ";", ":", "—", "-")


def _text(words: list[Word]) -> str:
    return " ".join(w.word for w in words)


def assign_words(segments: list[SttSegment], words: list[Word]) -> list[list[Word]]:
    """Give each word to the segment containing its midpoint, or the nearest one."""
    buckets: list[list[Word]] = [[] for _ in segments]
    if not segments:
        return buckets
    for w in words:
        mid = (w.start + w.end) / 2
        best = min(
            range(len(segments)),
            key=lambda i: 0.0 if segments[i].start <= mid <= segments[i].end
            else min(abs(mid - segments[i].start), abs(mid - segments[i].end)),
        )
        buckets[best].append(w)
    return buckets


def best_split(words: list[Word]) -> int:
    """Index i (1..n-1) to split words into words[:i] and words[i:]."""
    total = len(_text(words))
    best_i, best_score = 1, float("-inf")
    for i in range(1, len(words)):
        prev = words[i - 1].word
        score = 0.0
        if prev.endswith(_STRONG_PUNCT):
            score += 3.0
        elif prev.endswith(_WEAK_PUNCT):
            score += 1.5
        score += min(words[i].start - words[i - 1].end, 1.0) * 2.0  # pause, capped
        left = len(_text(words[:i]))
        score -= abs(left - (total - left - 1)) / total * 2.0  # prefer balanced halves
        if score > best_score:
            best_i, best_score = i, score
    return best_i


def _split(words: list[Word], max_chars: int) -> list[list[Word]]:
    if len(words) < 2 or len(_text(words)) <= max_chars:
        return [words]
    i = best_split(words)
    return _split(words[:i], max_chars) + _split(words[i:], max_chars)


def resegment(stt: SttResult, max_chars: int = MAX_SEGMENT_CHARS) -> list[Segment]:
    out: list[Segment] = []
    for seg, words in zip(stt.segments, assign_words(stt.segments, stt.words)):
        if len(seg.text) <= max_chars or len(words) < 2:
            chunks = [(seg.start, seg.end, seg.text, words)]
        else:
            chunks = [(c[0].start, c[-1].end, _text(c), c) for c in _split(words, max_chars)]
        for start, end, text, chunk_words in chunks:
            out.append(Segment(
                id=len(out), start=start, end=end, source_lang=stt.language,
                original_text=text, words=list(chunk_words),
            ))
    return out
