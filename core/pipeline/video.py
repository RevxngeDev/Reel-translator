"""Video path: speech -> bilingual subtitles (D-001..D-021), plus static on-screen
text detection (D-025).
"""

from __future__ import annotations

import logging
import re
import subprocess
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from pathlib import Path

from core import SUPPORTED_LANGS, transcript
from core.audio import extract_audio
from core.errors import NoSpeechError
from core.ocr.base import ImageTextReader
from core.pipeline.common import TextPair, check_languages, main_language, translate_texts
from core.render import srt_bilingual, study_transcript, video_subtitled
from core.render.layout import build_cues, violations
from core.resegment import resegment
from core.stt.base import SpeechToText
from core.translate.base import Translator

log = logging.getLogger(__name__)

# Three frames in one OCR call; text seen in at least two of them counts as static.
# Two frames proved fragile: one bad OCR read was enough to lose the text.
FRAME_POSITIONS = (0.2, 0.5, 0.8)
SPEECH_OVERLAP = 0.7  # on-screen text whose words are mostly spoken = burned-in captions
# OCR of two frames of the same static text can differ slightly ("estan" vs "es tan").
FRAME_SIMILARITY = 0.85


@dataclass
class VideoReport:
    video_path: Path | None  # None only when rendering was skipped (render_video=False)
    source_lang: str
    target_lang: str
    on_screen: list[TextPair] = field(default_factory=list)
    transcript_path: Path | None = None
    srt_path: Path | None = None
    study_path: Path | None = None
    video_bytes: int = 0
    video_width: int = 0
    video_height: int = 0
    video_seconds: float = 0.0
    segments: int = 0
    cues: int = 0
    layout_violations: list[str] = field(default_factory=list)
    audio_seconds: float = 0.0
    llm_tokens: int = 0
    llm_model: str = ""
    word_timestamps: bool = False


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _norm(text: str) -> str:
    return " ".join(_words(text))


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= FRAME_SIMILARITY


def static_blocks(frames: list[list[str]], speech: str) -> list[str]:
    """Blocks seen (allowing small OCR differences) in at least two frames and not
    mostly contained in the speech. Each static text is returned once, in order."""
    normed = [[_norm(b) for b in blocks] for blocks in frames]
    spoken = set(_words(speech))
    out: list[str] = []
    chosen: list[str] = []
    for i, blocks in enumerate(frames):
        for block, norm in zip(blocks, normed[i]):
            words = _words(block)
            if not words or any(_similar(norm, c) for c in chosen):
                continue
            if not any(_similar(norm, other) for j, others in enumerate(normed) if j != i for other in others):
                continue
            if spoken and sum(w in spoken for w in words) / len(words) >= SPEECH_OVERLAP:
                continue
            out.append(block)
            chosen.append(norm)
    return out


def _extract_frames(video: Path, work_dir: Path) -> list[Path]:
    _, _, duration = video_subtitled.probe(video)
    frames = []
    for pos in FRAME_POSITIONS:
        frame = work_dir / f"frame{int(pos * 100)}.jpg"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{duration * pos:.2f}",
             "-i", str(video), "-frames:v", "1", str(frame)],
            capture_output=True, check=True,
        )
        frames.append(frame)
    return frames


def detect_on_screen_text(video: Path, work_dir: Path, ocr: ImageTextReader, speech: str) -> tuple[str, list[str]]:
    """(language, static text blocks). Never raises: detection is best effort."""
    try:
        texts = ocr.read(_extract_frames(video, work_dir))
        blocks = static_blocks([t.blocks for t in texts], speech)
        language = main_language([t.language for t in texts])
        log.info("on-screen text: blocks per frame %s, %d static (lang %r)",
                 [len(t.blocks) for t in texts], len(blocks), language)
        return language, blocks
    except Exception as exc:  # noqa: BLE001 — a failed detection must not fail the reel
        log.warning("on-screen text detection skipped: %s: %s", type(exc).__name__, exc)
        return "", []


def _translate_on_screen(lang: str, blocks: list[str], target_lang: str, translator: Translator) -> tuple[list[TextPair], int]:
    if not blocks or lang not in SUPPORTED_LANGS or lang == target_lang:
        return [], 0
    return translate_texts(blocks, lang, target_lang, translator)


def _render(cues, video: Path, out_dir: Path, name: str, work_dir: Path,
            overlay: list[str]) -> tuple[Path, int, int, float]:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = video_subtitled.render(cues, video, out_dir / f"{name}.mp4", work_dir, overlay=overlay)
    width, height, seconds = video_subtitled.probe(path)
    return path, width, height, seconds


def process_video(
    video: Path,
    target_lang: str,
    *,
    name: str,
    work_dir: Path,
    out_dir: Path,
    stt: SpeechToText,
    translator: Translator,
    ocr: ImageTextReader | None = None,
    render_video: bool = True,
) -> VideoReport:
    work_dir.mkdir(parents=True, exist_ok=True)
    audio = extract_audio(video, work_dir)
    stt_result = stt.transcribe(audio)
    speech = " ".join(s.text for s in stt_result.segments)
    screen_lang, screen_blocks = detect_on_screen_text(video, work_dir, ocr, speech) if ocr else ("", [])

    if not stt_result.segments:
        if not screen_blocks:
            raise NoSpeechError("No speech or on-screen text in the video")
        check_languages(screen_lang, target_lang)
        pairs, tokens = translate_texts(screen_blocks, screen_lang, target_lang, translator)
        report = VideoReport(video_path=None, source_lang=screen_lang, target_lang=target_lang,
                             on_screen=pairs, audio_seconds=stt_result.duration, llm_tokens=tokens)
        if render_video:  # no speech cues: the on-screen translation goes at the bottom (D-027)
            path, report.video_width, report.video_height, report.video_seconds = _render(
                [], video, out_dir, name, work_dir, [p.translated for p in pairs])
            report.video_path, report.video_bytes = path, path.stat().st_size
        return report

    source_lang = stt_result.language
    check_languages(source_lang, target_lang)
    segments = resegment(stt_result)
    result = translator.translate(segments, source_lang, target_lang)
    for seg in segments:
        seg.translated_text = result.translations[seg.id]
    on_screen, screen_tokens = _translate_on_screen(screen_lang, screen_blocks, target_lang, translator)

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
    video_path, width, height, seconds = None, 0, 0, 0.0
    if render_video:  # on-screen translation burned at the top, speech at the bottom (D-027)
        video_path, width, height, seconds = _render(
            cues, video, out_dir, name, work_dir, [p.translated for p in on_screen])

    return VideoReport(
        video_path=video_path,
        source_lang=source_lang,
        target_lang=target_lang,
        on_screen=on_screen,
        transcript_path=transcript_path,
        srt_path=srt_path,
        study_path=study_path,
        video_bytes=video_path.stat().st_size if video_path else 0,
        video_width=width,
        video_height=height,
        video_seconds=seconds,
        segments=len(segments),
        cues=len(cues),
        layout_violations=violations(cues),
        audio_seconds=stt_result.duration,
        llm_tokens=result.tokens + screen_tokens,
        llm_model=result.model,
        word_timestamps=bool(stt_result.words),
    )
