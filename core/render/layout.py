"""Turns transcript segments into subtitle cues of at most 2 lines x 42 chars per
language (Phase 1 gate). Shared by every subtitle renderer.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.resegment import best_split
from core.transcript import Segment

MAX_LINE_CHARS = 42
MAX_LINES = 2


@dataclass
class Cue:
    start: float
    end: float
    original: list[str]
    translation: list[str]


def wrap(text: str, width: int = MAX_LINE_CHARS, max_lines: int = MAX_LINES) -> list[str] | None:
    """Balanced wrap into at most `max_lines` lines of `width`; None if it cannot fit."""
    text = " ".join(text.split())
    if len(text) <= width:
        return [text]
    if max_lines < 2:
        return None
    tokens = text.split(" ")
    best: tuple[int, list[str]] | None = None
    for i in range(1, len(tokens)):
        first = " ".join(tokens[:i])
        if len(first) > width:
            break
        rest = wrap(" ".join(tokens[i:]), width, max_lines - 1)
        if rest is None:
            continue
        lines = [first, *rest]
        spread = max(map(len, lines)) - min(map(len, lines))
        if best is None or spread < best[0]:
            best = (spread, lines)
    return best[1] if best else None


def _split_text_at_ratio(text: str, ratio: float) -> tuple[str, str]:
    tokens = text.split()
    if len(tokens) < 2:
        return text, ""
    target = len(text) * ratio
    pos, best_i, best_d = 0, 1, float("inf")
    for i in range(1, len(tokens)):
        pos += len(tokens[i - 1]) + 1
        if abs(pos - target) < best_d:
            best_i, best_d = i, abs(pos - target)
    return " ".join(tokens[:best_i]), " ".join(tokens[best_i:])


def _halves(seg: Segment) -> tuple[Segment, Segment] | None:
    """Split a segment in time; the translation is cut at the same text proportion."""
    words = seg.words
    if len(words) >= 2:
        i = best_split(words)
        left_w, right_w = words[:i], words[i:]
        left_o, right_o = " ".join(w.word for w in left_w), " ".join(w.word for w in right_w)
        mid = (left_w[-1].end + right_w[0].start) / 2
    else:
        left_o, right_o = _split_text_at_ratio(seg.original_text, 0.5)
        if not right_o:
            return None
        left_w, right_w = [], []
        mid = (seg.start + seg.end) / 2
    ratio = len(left_o) / (len(left_o) + len(right_o) + 1)
    left_t, right_t = _split_text_at_ratio(seg.translated_text or "", ratio)
    if not right_t and seg.translated_text:
        return None
    mk = lambda s, e, o, t, w: Segment(seg.id, s, e, seg.source_lang, o, t, w)  # noqa: E731
    return mk(seg.start, mid, left_o, left_t, left_w), mk(mid, seg.end, right_o, right_t, right_w)


def _force_wrap(text: str) -> list[str]:
    """Last resort for an unsplittable text: hard-cut into 42-char lines."""
    return [text[i : i + MAX_LINE_CHARS] for i in range(0, len(text), MAX_LINE_CHARS)][:MAX_LINES]


def build_cues(segments: list[Segment]) -> list[Cue]:
    cues: list[Cue] = []
    pending = list(segments)
    while pending:
        seg = pending.pop(0)
        orig = wrap(seg.original_text)
        trans = wrap(seg.translated_text) if seg.translated_text else []
        if orig is not None and trans is not None:
            cues.append(Cue(seg.start, seg.end, orig, trans))
            continue
        halves = _halves(seg)
        if halves is None:
            cues.append(Cue(seg.start, seg.end, orig or _force_wrap(seg.original_text),
                            trans if trans is not None else _force_wrap(seg.translated_text or "")))
            continue
        pending[0:0] = list(halves)
    return cues


def violations(cues: list[Cue]) -> list[str]:
    """Phase 1 gate check: describe every cue breaking the 2 x 42 rule."""
    out = []
    for n, c in enumerate(cues, start=1):
        for label, lines in (("original", c.original), ("translation", c.translation)):
            if len(lines) > MAX_LINES or any(len(line) > MAX_LINE_CHARS for line in lines):
                out.append(f"cue {n} {label}: {lines}")
    return out


__all__ = ["Cue", "build_cues", "violations", "wrap", "MAX_LINE_CHARS", "MAX_LINES"]
