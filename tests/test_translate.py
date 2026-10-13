import json
from types import SimpleNamespace

import pytest

from core.errors import TranslationError, TranslationMismatchError
from core.transcript import Segment
from core.translate import FallbackTranslator, GroqLlmTranslator, TranslationResult


def _segments(n):
    return [Segment(id=i, start=i, end=i + 1, source_lang="es", original_text=f"hola {i}") for i in range(n)]


class FakeClient:
    """Mimics groq.Groq().chat.completions.create, answering from a function."""

    def __init__(self, answer):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._answer = answer

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        sent = json.loads(kwargs["messages"][0]["content"].split("Input segments (JSON):\n", 1)[1])
        content = json.dumps({"segments": self._answer(sent)})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(total_tokens=100),
        )


def echo(sent):
    return [{"id": s["id"], "text": s["text"].upper()} for s in sent]


def test_translates_all_segments_in_batches():
    client = FakeClient(echo)
    t = GroqLlmTranslator("m", client=client, batch_size=2)
    result = t.translate(_segments(5), "es", "en")
    assert result.translations == {i: f"HOLA {i}" for i in range(5)}
    assert result.tokens == 300  # 3 batches
    assert len(client.calls) == 3


def test_dropped_segment_fails_loudly():
    t = GroqLlmTranslator("m", client=FakeClient(lambda sent: echo(sent)[:-1]))
    with pytest.raises(TranslationMismatchError):
        t.translate(_segments(3), "es", "en")


def test_reordered_segments_fail_loudly():
    t = GroqLlmTranslator("m", client=FakeClient(lambda sent: list(reversed(echo(sent)))))
    with pytest.raises(TranslationMismatchError):
        t.translate(_segments(3), "es", "en")


class Stub:
    def __init__(self, exc=None):
        self.exc = exc
        self.called = False

    def translate(self, segments, source_lang, target_lang):
        self.called = True
        if self.exc:
            raise self.exc
        return TranslationResult(translations={s.id: "ok" for s in segments}, tokens=1, model="stub")


def test_fallback_on_provider_failure():
    second = Stub()
    result = FallbackTranslator([Stub(TranslationError("rate limit")), second]).translate(_segments(1), "es", "en")
    assert second.called and result.model == "stub"


def test_mismatch_does_not_fall_back():
    second = Stub()
    with pytest.raises(TranslationMismatchError):
        FallbackTranslator([Stub(TranslationMismatchError("x")), second]).translate(_segments(1), "es", "en")
    assert not second.called


def test_all_providers_failing_raises():
    with pytest.raises(TranslationError, match="All translation providers failed"):
        FallbackTranslator([Stub(TranslationError("a")), Stub(TranslationError("b"))]).translate(_segments(1), "es", "en")
