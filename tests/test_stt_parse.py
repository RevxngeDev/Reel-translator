from core.stt.groq_whisper import normalize_language, parse_verbose_json


def test_parses_segments_words_and_language():
    data = {
        "language": "Spanish",
        "duration": 4.5,
        "segments": [
            {"start": 0.0, "end": 2.0, "text": " Hola amigos "},
            {"start": 2.0, "end": 2.5, "text": "   "},
            {"start": 2.5, "end": 4.5, "text": "¿Qué tal?"},
        ],
        "words": [{"word": "Hola", "start": 0.0, "end": 0.5}],
    }
    r = parse_verbose_json(data)
    assert r.language == "es"
    assert [s.text for s in r.segments] == ["Hola amigos", "¿Qué tal?"]
    assert r.duration == 4.5
    assert len(r.words) == 1


def test_missing_words_and_duration():
    r = parse_verbose_json({"language": "en", "segments": [{"start": 0, "end": 3, "text": "hi"}]})
    assert r.words == []
    assert r.duration == 3


def test_normalize_language():
    assert normalize_language("russian") == "ru"
    assert normalize_language("EN") == "en"
    assert normalize_language("french") == "french"
    assert normalize_language(None) == ""
