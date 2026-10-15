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


def test_overlay_at_top_with_speech_and_at_bottom_without():
    cues = build_cues([_seg("Hola", "Hello")])
    with_speech = build_ass(cues, 1080, 1920, overlay=["When we live with other couples"], duration=12.5)
    style = next(line for line in with_speech.splitlines() if line.startswith("Style: Overlay"))
    assert style.split(",")[18] == "8"  # top-centre alignment
    assert "Dialogue: 1,0:00:00.00,0:00:12.50,Overlay,,0,0,0,,When we live with other couples" in with_speech
    no_speech = build_ass([], 1080, 1920, overlay=["Only text"], duration=3)
    style = next(line for line in no_speech.splitlines() if line.startswith("Style: Overlay"))
    assert style.split(",")[18] == "2"  # bottom-centre when there are no speech cues


def test_long_overlay_is_wrapped_to_short_lines():
    text = "Una canción trágica sobre una mujer trans que es abandonada por su padre y muere sola en un hospital"
    ass = build_ass([], 1080, 1920, overlay=[text], duration=5)
    event = next(line for line in ass.splitlines() if ",Overlay," in line)
    lines = event.split(",,0,0,0,,", 1)[1].split("\\N")
    assert len(lines) > 1 and all(len(line) <= 42 for line in lines)
