from core.render.layout import build_cues, violations, wrap
from core.render.video_subtitled import build_ass
from core.transcript import Segment, Word


def test_wrap_short_text_single_line():
    assert wrap("Hola amigos") == ["Hola amigos"]


def test_wrap_balanced_two_lines():
    lines = wrap("Listen carefully, the most important aspect of a relationship")
    assert len(lines) == 2 and all(len(line) <= 42 for line in lines)


def test_wrap_too_long_returns_none():
    assert wrap("word " * 30) is None


def _seg(orig, trans, start=0.0, step=0.3):
    words, t = [], start
    for w in orig.split():
        words.append(Word(w, t, t + step - 0.05))
        t += step
    return Segment(0, start, t, "es", orig, trans, words)


def test_cue_split_in_time_when_translation_too_long():
    orig = "Pasado en mis experiencias, los primeros meses fueron increíbles."
    trans = ("Based on my own personal experiences, the very first three or four months "
             "with my wife were absolutely and completely amazing.")
    cues = build_cues([_seg(orig, trans)])
    assert len(cues) >= 2
    assert violations(cues) == []
    assert " ".join(" ".join(c.original) for c in cues) == orig
    assert " ".join(" ".join(c.translation) for c in cues) == trans
    assert cues[0].start == 0.0 and cues[0].end <= cues[1].start


def test_ass_has_both_styles_and_escapes_braces():
    cues = build_cues([_seg("Hola {amigos}", "Hello friends")])
    ass = build_ass(cues, 1080, 1920)
    assert "PlayResX: 1080" in ass and "Style: Trans,Arial" in ass
    assert "Hola (amigos)\\N{\\rTrans}Hello friends" in ass
