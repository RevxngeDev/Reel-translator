"""Orchestrates one job: fetch the post, then dispatch by content (D-025).

1 video -> video path; images only -> image path; mixed carousel -> both.
Media files are written to `work_dir`; deleting them is the caller's policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core import SUPPORTED_LANGS
from core.errors import FetchError, NoTextError, UnsupportedLanguageError
from core.ocr.base import ImageTextReader
from core.pipeline.images import ImagePostReport, process_images
from core.pipeline.video import VideoReport, process_video
from core.source.base import MediaSource
from core.stt.base import SpeechToText
from core.translate.base import Translator


@dataclass
class JobResult:
    videos: list[VideoReport] = field(default_factory=list)
    image_post: ImagePostReport | None = None

    @property
    def kind(self) -> str:
        if self.image_post and self.videos:
            return "mixed"
        return "images" if self.image_post else "video"


def run_job(
    url: str,
    target_lang: str,
    *,
    name: str,
    work_dir: Path,
    out_dir: Path,
    source: MediaSource,
    stt: SpeechToText,
    translator: Translator,
    ocr: ImageTextReader | None = None,
    render_video: bool = True,
) -> JobResult:
    if target_lang not in SUPPORTED_LANGS:
        raise UnsupportedLanguageError(target_lang, role="target")

    media = source.fetch(url, work_dir / "fetch")
    if media.empty:
        raise FetchError("The post has no video or image")
    if media.images and ocr is None:
        raise FetchError("The post contains images but no OCR reader is configured")

    result = JobResult()
    if media.images:
        try:
            result.image_post = process_images(media.images, target_lang, name=name,
                                               out_dir=out_dir, ocr=ocr, translator=translator)
        except NoTextError:
            if not media.videos:
                raise  # a carousel's text-less images are fine if it has videos
    for i, video in enumerate(media.videos):
        suffix = f"-v{i + 1}" if len(media.videos) > 1 or media.images else ""
        result.videos.append(process_video(
            video, target_lang, name=f"{name}{suffix}", work_dir=work_dir / f"video{i + 1}",
            out_dir=out_dir, stt=stt, translator=translator, ocr=ocr, render_video=render_video,
        ))
    return result
