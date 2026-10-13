"""Orchestrates one job end to end and writes the transcript JSON.

Media files are written to `work_dir`; deleting them is the caller's policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core import SUPPORTED_LANGS, transcript
from core.audio import extract_audio
from core.errors import SameLanguageError, SpeechToTextError, UnsupportedLanguageError
from core.render import srt_bilingual
from core.source.base import VideoSource
from core.stt.base import SpeechToText
from core.transcript import Segment
from core.translate.base import Translator


@dataclass
class JobReport:
    transcript_path: Path
    srt_path: Path
    source_lang: str
    target_lang: str
    segments: int
    audio_seconds: float
    llm_tokens: int
    llm_model: str
    word_timestamps: bool


def run_job(
    url: str,
    target_lang: str,
    *,
    name: str,
    work_dir: Path,
    out_dir: Path,
    source: VideoSource,
    stt: SpeechToText,
    translator: Translator,
) -> JobReport:
    if target_lang not in SUPPORTED_LANGS:
        raise UnsupportedLanguageError(target_lang, role="target")

    video = source.fetch(url, work_dir)
    audio = extract_audio(video, work_dir)
    stt_result = stt.transcribe(audio)

    source_lang = stt_result.language
    if source_lang not in SUPPORTED_LANGS:
        raise UnsupportedLanguageError(source_lang)
    if source_lang == target_lang:
        raise SameLanguageError(f"The video is already in {target_lang}")
    if not stt_result.segments:
        raise SpeechToTextError("No speech detected in the video")

    segments = [
        Segment(id=i, start=s.start, end=s.end, source_lang=source_lang, original_text=s.text)
        for i, s in enumerate(stt_result.segments)
    ]
    result = translator.translate(segments, source_lang, target_lang)
    for seg in segments:
        seg.translated_text = result.translations[seg.id]

    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / f"{name}.json"
    srt_path = out_dir / f"{name}.srt"
    transcript.save(segments, transcript_path)
    srt_bilingual.write(segments, srt_path)

    return JobReport(
        transcript_path=transcript_path,
        srt_path=srt_path,
        source_lang=source_lang,
        target_lang=target_lang,
        segments=len(segments),
        audio_seconds=stt_result.duration,
        llm_tokens=result.tokens,
        llm_model=result.model,
        word_timestamps=bool(stt_result.words),
    )
