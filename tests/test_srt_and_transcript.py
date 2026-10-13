from core import transcript
from core.render import srt_bilingual
from core.transcript import Segment


def test_transcript_roundtrip(tmp_path):
    segs = [Segment(id=0, start=0.0, end=1.5, source_lang="ru", original_text="Привет", translated_text="Hola")]
    path = tmp_path / "t.json"
    transcript.save(segs, path)
    assert transcript.load(path) == segs
    assert "Привет" in path.read_text(encoding="utf-8")  # not escaped


def test_srt_bilingual_block():
    segs = [
        Segment(id=0, start=0.0, end=1.5, source_lang="es", original_text="Hola", translated_text="Hello"),
        Segment(id=1, start=61.25, end=3725.009, source_lang="es", original_text="Adiós", translated_text="Bye"),
    ]
    assert srt_bilingual.render(segs) == (
        "1\n00:00:00,000 --> 00:00:01,500\nHola\nHello\n"
        "\n"
        "2\n00:01:01,250 --> 01:02:05,009\nAdiós\nBye\n"
    )
