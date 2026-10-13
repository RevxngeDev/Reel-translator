from core.resegment import assign_words, resegment
from core.stt.base import SttResult, SttSegment
from core.transcript import Word


def _words(text, start=0.0, step=0.3, pause_after=None):
    out, t = [], start
    for i, w in enumerate(text.split()):
        out.append(Word(w, t, t + step - 0.05))
        t += step
        if pause_after is not None and i == pause_after:
            t += 1.0
    return out


def test_words_go_to_segment_by_midpoint():
    segs = [SttSegment(0.0, 2.8, "a b"), SttSegment(4.4, 5.5, "c")]
    words = [Word("a", 0.3, 1.1), Word("b", 2.4, 2.7), Word("c", 4.34, 5.78)]
    assert assign_words(segs, words) == [words[:2], words[2:]]


def test_short_segment_kept_as_is():
    words = _words("Ahora, dígame cómo la paro.")
    r = resegment(SttResult("es", [SttSegment(0.0, 2.0, "Ahora, dígame cómo la paro.")], 2.0, words))
    assert len(r) == 1
    assert r[0].original_text == "Ahora, dígame cómo la paro."
    assert r[0].words == words


def test_long_segment_split_at_punctuation_with_contiguous_ids():
    text = ("Escúcheme bien, la faceta más importante en una relación es la faceta "
            "donde empiezan a pelear. Donde empiezan a discutir todos los días.")
    words = _words(text)
    r = resegment(SttResult("es", [SttSegment(0.0, 9.0, text), SttSegment(10, 11, "Fin.")], 11.0,
                            words + [Word("Fin.", 10.1, 10.9)]))
    assert [s.id for s in r] == list(range(len(r)))
    assert all(len(s.original_text) <= 64 for s in r)
    assert " ".join(s.original_text for s in r[:-1]) == text  # nothing lost or reordered
    assert any(s.original_text.endswith("pelear.") for s in r)
    for s in r[:-1]:  # split chunks take their timing from their words
        assert s.start == s.words[0].start and s.end == s.words[-1].end
    assert (r[-1].start, r[-1].end) == (10, 11)  # unsplit segment keeps STT timing
