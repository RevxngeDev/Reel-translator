from core import transcript
from core.render import srt_bilingual, study_transcript
from core.render.layout import Cue
from core.transcript import Segment, Word


def test_transcript_roundtrip_with_words(tmp_path):
    segs = [Segment(id=0, start=0.0, end=1.5, source_lang="ru", original_text="Привет",
                    translated_text="Hola", words=[Word("Привет", 0.1, 1.4)])]
    path = tmp_path / "t.json"
    transcript.save(segs, path)
    assert transcript.load(path) == segs
    assert "Привет" in path.read_text(encoding="utf-8")  # not escaped


def test_srt_bilingual_block():
    cues = [
        Cue(0.0, 1.5, ["Hola"], ["Hello"]),
        Cue(61.25, 3725.009, ["Adiós a todos", "mis amigos"], ["Bye"]),
    ]
    assert srt_bilingual.render(cues) == (
        "1\n00:00:00,000 --> 00:00:01,500\nHola\nHello\n"
        "\n"
        "2\n00:01:01,250 --> 01:02:05,009\nAdiós a todos\nmis amigos\nBye\n"
    )


def test_study_transcript():
    segs = [Segment(0, 65.2, 67.0, "es", "Hola", "Hello")]
    text = study_transcript.render(segs, "es", "en")
    assert "[01:05] Hola\n        Hello\n" in text
