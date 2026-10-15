import shutil
import subprocess

import pytest

from core import transcript
from core.audio import extract_audio
from core.errors import NoSpeechError, NoTextError, SameLanguageError, UnsupportedLanguageError
from core.ocr.base import ImageText
from core.pipeline import run_job
from core.pipeline.video import static_blocks
from core.source.base import Media
from core.stt.base import SttResult, SttSegment, Word
from core.translate import TranslationResult

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def _make_video(path):
    """2-second synthetic video with a sine-tone audio track."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(path),
        ],
        check=True,
    )


class FakeSource:
    def __init__(self, videos=1, images=0):
        self.videos, self.images = videos, images

    def fetch(self, url, out_dir):
        from PIL import Image

        out_dir.mkdir(parents=True, exist_ok=True)
        media = Media()
        for i in range(self.images):
            p = out_dir / f"{i:03}.jpg"
            Image.new("RGB", (60, 80), "white").save(p)
            media.images.append(p)
        for i in range(self.videos):
            p = out_dir / f"v{i}.mp4"
            _make_video(p)
            media.videos.append(p)
        return media


class FakeOcr:
    """Returns preset texts in order; records how many images each read() got."""

    def __init__(self, texts):
        self.texts, self.calls = list(texts), []

    def read(self, images):
        self.calls.append(len(images))
        return [self.texts.pop(0) for _ in images]


class FakeStt:
    def __init__(self, language="es", silent=False):
        self.language, self.silent = language, silent

    def transcribe(self, audio_path):
        assert audio_path.suffix == ".flac" and audio_path.stat().st_size > 0
        if self.silent:
            return SttResult(language="", segments=[], duration=2.0)
        return SttResult(
            language=self.language,
            segments=[SttSegment(0.0, 1.0, "Hola"), SttSegment(1.0, 2.0, "amigos")],
            duration=2.0,
            words=[Word("Hola", 0.1, 0.9), Word("amigos", 1.1, 1.9)],
        )


class FakeTranslator:
    def translate(self, segments, source_lang, target_lang):
        return TranslationResult({s.id: s.original_text.upper() for s in segments}, tokens=42, model="fake")


def _run(tmp_path, stt=None, target="en", source=None, ocr=None):
    return run_job(
        "https://example.invalid/reel",
        target,
        name="job",
        work_dir=tmp_path / "work",
        out_dir=tmp_path / "out",
        source=source or FakeSource(),
        stt=stt or FakeStt(),
        translator=FakeTranslator(),
        ocr=ocr,
    )


@pytest.fixture
def tmp(tmp_path):
    (tmp_path / "work").mkdir()
    return tmp_path


def test_extract_audio_mono_16k(tmp_path):
    video = tmp_path / "v.mp4"
    _make_video(video)
    audio = extract_audio(video, tmp_path)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels",
         "-of", "csv=p=0", str(audio)],
        capture_output=True, text=True, check=True,
    )
    assert probe.stdout.strip() == "16000,1"


def test_full_job_writes_transcript_and_srt(tmp):
    result = _run(tmp)
    assert result.kind == "video" and result.image_post is None
    report = result.videos[0]
    segs = transcript.load(report.transcript_path)
    assert [(s.id, s.original_text, s.translated_text) for s in segs] == [(0, "Hola", "HOLA"), (1, "amigos", "AMIGOS")]
    assert "Hola\nHOLA" in report.srt_path.read_text(encoding="utf-8")
    assert report.source_lang == "es" and report.llm_tokens == 42 and report.word_timestamps
    assert segs[1].words[0].word == "amigos"
    assert report.layout_violations == []
    assert "HOLA" in report.study_path.read_text(encoding="utf-8")
    assert report.video_path.exists() and report.video_bytes > 0
    assert (report.video_width, report.video_height) == (320, 240) and report.video_seconds > 1.5


def test_unsupported_source_language_fails(tmp):
    with pytest.raises(UnsupportedLanguageError):
        _run(tmp, stt=FakeStt(language="fr"))


def test_same_language_fails(tmp):
    with pytest.raises(SameLanguageError):
        _run(tmp, target="es")


def test_unsupported_target_fails(tmp):
    with pytest.raises(UnsupportedLanguageError):
        _run(tmp, target="de")


def test_static_blocks_keeps_text_in_both_frames_not_spoken():
    a = ["POV: tu primer día", "Hola amigos", "@usuario"]
    b = ["POV: tu primer día!", "@usuario", "otra cosa"]
    assert static_blocks(a, b, speech="Hola amigos, ¿qué tal?") == ["POV: tu primer día", "@usuario"]


def test_static_blocks_tolerates_small_ocr_differences_between_frames():
    # Real case: the same overlay read as "no estan" in one frame and "no es tan" in the other.
    a = ["Cuando convivimos con otras parejas y nos damos cuenta que nuestra relación no estan tóxica como creíamos:"]
    b = ["Cuando convivimos con otras parejas y nos damos cuenta que nuestra relación no es tan tóxica como creíamos:"]
    assert static_blocks(a, b, speech="Voltea a ver, te estoy hablando") == a
    assert static_blocks(["Hola mundo"], ["Adiós a todos"], speech="") == []


def test_reel_on_screen_text_is_translated(tmp):
    ocr = FakeOcr([ImageText("es", ["Cuando convivimos"]), ImageText("es", ["Cuando convivimos"])])
    report = _run(tmp, ocr=ocr).videos[0]
    assert ocr.calls == [2]  # both frames in one read
    assert [(p.original, p.translated) for p in report.on_screen] == [("Cuando convivimos", "CUANDO CONVIVIMOS")]


def test_on_screen_detection_failure_does_not_fail_the_reel(tmp):
    class BrokenOcr:
        def read(self, images):
            raise RuntimeError("rate limited")
    report = _run(tmp, ocr=BrokenOcr()).videos[0]
    assert report.video_path.exists() and report.on_screen == []


def test_video_without_speech_but_with_on_screen_text(tmp):
    ocr = FakeOcr([ImageText("es", ["Solo texto"]), ImageText("es", ["Solo texto"])])
    report = _run(tmp, stt=FakeStt(silent=True), ocr=ocr).videos[0]
    assert report.video_path is None and report.on_screen[0].translated == "SOLO TEXTO"


def test_video_without_speech_or_text_fails(tmp):
    with pytest.raises(NoSpeechError):
        _run(tmp, stt=FakeStt(silent=True), ocr=FakeOcr([ImageText("", []), ImageText("", [])]))


def test_image_post_translates_blocks_per_image(tmp):
    ocr = FakeOcr([ImageText("en", ["Pick one"]), ImageText("", []), ImageText("en", ["A) Yes", "B) No"])])
    result = _run(tmp, target="es", source=FakeSource(videos=0, images=3), ocr=ocr)
    post = result.image_post
    assert result.kind == "images" and result.videos == [] and post.source_lang == "en"
    assert [[p.translated for p in slide] for slide in post.slides] == [["PICK ONE"], [], ["A) YES", "B) NO"]]
    assert post.result_path.exists()


def test_image_post_without_text_fails(tmp):
    with pytest.raises(NoTextError):
        _run(tmp, source=FakeSource(videos=0, images=2), ocr=FakeOcr([ImageText("", []), ImageText("", [])]))


def test_mixed_carousel_with_textless_images_still_processes_the_video(tmp):
    ocr = FakeOcr([ImageText("", []), ImageText("", []), ImageText("", [])])  # 1 image + 2 frames
    result = _run(tmp, source=FakeSource(videos=1, images=1), ocr=ocr)
    assert result.image_post is None and len(result.videos) == 1 and result.videos[0].video_path.exists()


def test_image_post_in_target_language_fails(tmp):
    with pytest.raises(SameLanguageError):
        _run(tmp, target="en", source=FakeSource(videos=0, images=1), ocr=FakeOcr([ImageText("en", ["Hi"])]))
