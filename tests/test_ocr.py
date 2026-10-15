import json
from types import SimpleNamespace

import pytest
from PIL import Image

from core.errors import OcrError
from core.ocr import grid
from core.ocr.groq_vision import GroqVisionReader, split_blocks


def _images(tmp_path, sizes):
    paths = []
    for i, size in enumerate(sizes):
        p = tmp_path / f"{i}.jpg"
        Image.new("RGB", size, "gray").save(p)
        paths.append(p)
    return paths


def test_layout():
    assert [grid.layout(n) for n in (1, 2, 3, 4)] == [(1, 1), (2, 1), (2, 2), (2, 2)]
    with pytest.raises(ValueError):
        grid.layout(5)


def test_pack_sizes(tmp_path):
    assert grid.pack(_images(tmp_path, [(1080, 1350)])).size == (1080, 1350)
    four = grid.pack(_images(tmp_path, [(1080, 1350)] * 4))
    assert four.size == (2 * 1080 + grid.GUTTER, 2 * 1350 + grid.GUTTER)
    mixed = grid.pack(_images(tmp_path, [(2000, 1000), (500, 1000)]))
    assert mixed.size == (2 * 1080 + grid.GUTTER, 1080 * 1000 // 500)


def test_split_blocks_assigns_prefixed_and_follows_last_slide():
    blocks = ["[1] pick your favorite", "flamingo", "[3] Which version?", "[9] out of range", "[2] A) Yes"]
    assert split_blocks(blocks, 3) == [["pick your favorite", "flamingo"], ["A) Yes"], ["Which version?", "out of range"]]
    assert split_blocks(["  hello ", ""], 1) == [["hello"]]


class FakeClient:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.answers.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_reader_packs_four_per_call_and_maps_slides(tmp_path):
    answers = [
        json.dumps({"language": "en", "blocks": ["[1] one", "[2] two", "[4] four"]}),
        json.dumps({"language": "none", "blocks": []}),
    ]
    client = FakeClient(answers)
    texts = GroqVisionReader(client=client).read(_images(tmp_path, [(100, 100)] * 5))
    assert len(client.calls) == 2
    assert [(t.language, t.blocks) for t in texts] == [
        ("en", ["one"]), ("en", ["two"]), ("", []), ("en", ["four"]), ("", []),
    ]
    first, second = client.calls
    assert "grid of 4" in first["messages"][0]["content"][0]["text"]
    assert "grid" not in second["messages"][0]["content"][0]["text"]  # single image
    assert first["max_completion_tokens"] <= 1000  # observed free-tier output cap per minute


def test_reader_rejects_malformed_json(tmp_path):
    with pytest.raises(OcrError):
        GroqVisionReader(client=FakeClient(["not json"])).read(_images(tmp_path, [(10, 10)]))
