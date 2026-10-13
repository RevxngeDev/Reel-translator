"""Orchestrates one job end to end and writes the transcript JSON.

Media files are written to `work_dir`; deleting them is the caller's policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core import SUPPORTED_LANGS, transcript
from core.audio import extract_audio
from core.errors import NoSpeechError, SameLanguageError, UnsupportedLanguageError
from core.render import srt_bilingual, study_transcript, video_subtitled
from core.render.layout import build_cues, violations
from core.resegment import resegment
from core.source.base import VideoSource
from core.stt.base import SpeechToText
from core.translate.base import Translator


@dataclass
class JobReport:
    transcript_path: Path
    srt_path: Path
    study_path: Path
    video_path: Path | None
    video_bytes: int
    source_lang: str
    target_lang: str
    segments: int
    cues: int
    layout_violations: list[str]
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
    render_video: bool = True,
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
        raise NoSpeechError("No speech detected in the video")

    segments = resegment(stt_result)
    result = translator.translate(segments, source_lang, target_lang)
    for seg in segments:
        seg.translated_text = result.translations[seg.id]

    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / f"{name}.json"
    transcript.save(segments, transcript_path)

    # Renderers read only the transcript (D-001).
    segments = transcript.load(transcript_path)
    cues = build_cues(segments)
    srt_path = out_dir / f"{name}.srt"
    srt_bilingual.write(cues, srt_path)
    study_path = out_dir / f"{name}.txt"
    study_transcript.write(segments, source_lang, target_lang, study_path)
    video_path = None
    if render_video:
        video_path = video_subtitled.render(cues, video, out_dir / f"{name}.mp4", work_dir)

    return JobReport(
        transcript_path=transcript_path,
        srt_path=srt_path,
        study_path=study_path,
        video_path=video_path,
        video_bytes=video_path.stat().st_size if video_path else 0,
        source_lang=source_lang,
        target_lang=target_lang,
        segments=len(segments),
        cues=len(cues),
        layout_violations=violations(cues),
        audio_seconds=stt_result.duration,
        llm_tokens=result.tokens,
        llm_model=result.model,
        word_timestamps=bool(stt_result.words),
    )

