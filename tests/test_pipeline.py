import shutil
import subprocess

import pytest

from core import transcript
from core.audio import extract_audio
from core.errors import SameLanguageError, UnsupportedLanguageError
from core.pipeline import run_job
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
    def fetch(self, url, out_dir):
        path = out_dir / "video.mp4"
        _make_video(path)
        return path


class FakeStt:
    def __init__(self, language="es"):
        self.language = language

    def transcribe(self, audio_path):
        assert audio_path.suffix == ".flac" and audio_path.stat().st_size > 0
        return SttResult(
            language=self.language,
            segments=[SttSegment(0.0, 1.0, "Hola"), SttSegment(1.0, 2.0, "amigos")],
            duration=2.0,
            words=[Word("Hola", 0.1, 0.9), Word("amigos", 1.1, 1.9)],
        )


class FakeTranslator:
    def translate(self, segments, source_lang, target_lang):
        return TranslationResult({s.id: s.original_text.upper() for s in segments}, tokens=42, model="fake")


def _run(tmp_path, stt=None, target="en"):
    return run_job(
        "https://example.invalid/reel",
        target,
        name="job",
        work_dir=tmp_path / "work",
        out_dir=tmp_path / "out",
        source=FakeSource(),
        stt=stt or FakeStt(),
        translator=FakeTranslator(),
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
    report = _run(tmp)
    segs = transcript.load(report.transcript_path)
    assert [(s.id, s.original_text, s.translated_text) for s in segs] == [(0, "Hola", "HOLA"), (1, "amigos", "AMIGOS")]
    assert "Hola\nHOLA" in report.srt_path.read_text(encoding="utf-8")
    assert report.source_lang == "es" and report.llm_tokens == 42 and report.word_timestamps
    assert segs[1].words[0].word == "amigos"
    assert report.layout_violations == []
    assert "HOLA" in report.study_path.read_text(encoding="utf-8")
    assert report.video_path.exists() and report.video_bytes > 0


def test_unsupported_source_language_fails(tmp):
    with pytest.raises(UnsupportedLanguageError):
        _run(tmp, stt=FakeStt(language="fr"))


def test_same_language_fails(tmp):
    with pytest.raises(SameLanguageError):
        _run(tmp, target="es")


def test_unsupported_target_fails(tmp):
    with pytest.raises(UnsupportedLanguageError):
        _run(tmp, target="de")
