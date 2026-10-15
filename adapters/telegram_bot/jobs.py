"""Runs one queued job: pipeline in a worker thread, delivery, and guaranteed cleanup.

Delivery (D-019, D-025): subtitled videos; image posts as the original images plus
one bilingual message per image; on-screen text of reels in the video message.
Every job ends with a message to the user (Phase 2 gate) and with no media left on
disk: all job files live in one temporary directory removed at the end.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol

from telegram import InputMediaPhoto

from adapters.telegram_bot import i18n
from adapters.telegram_bot.db import Database
from core import pipeline
from core.pipeline import ImagePostReport, JobResult, TextPair, VideoReport

log = logging.getLogger(__name__)

TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024  # standard Bot API upload limit (D-006/D-010)
MESSAGE_LIMIT = 4000  # Telegram allows 4096 characters per message
CAPTION_LIMIT = 1000  # Telegram allows 1024 characters per caption
MEDIA_GROUP_MAX = 10


class Sender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object: ...
    async def send_video(self, chat_id: int, video: object, **kwargs: object) -> object: ...
    async def send_photo(self, chat_id: int, photo: object, **kwargs: object) -> object: ...
    async def send_media_group(self, chat_id: int, media: list, **kwargs: object) -> object: ...


PipelineRunner = Callable[..., JobResult]


def format_pairs(pairs: list[TextPair]) -> str:
    return "\n\n".join(f"{p.original}\n➜ {p.translated}" for p in pairs)


def chunks(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Split on paragraph boundaries so each piece fits in one Telegram message."""
    out, current = [], ""
    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            out.append(current)
        while len(para) > limit:
            out.append(para[:limit])
            para = para[limit:]
        current = para
    if current:
        out.append(current)
    return out


async def _send_text(bot: Sender, chat_id: int, text: str) -> None:
    for piece in chunks(text):
        await bot.send_message(chat_id, piece)


async def _deliver_images(bot: Sender, chat_id: int, post: ImagePostReport, ui: str) -> None:
    caption = i18n.t("done", ui, source=post.source_lang, target=post.target_lang)
    with ExitStack() as stack:
        files = [stack.enter_context(p.open("rb")) for p in post.images]
        if len(files) == 1:
            await bot.send_photo(chat_id, files[0], caption=caption)
        else:
            for start in range(0, len(files), MEDIA_GROUP_MAX):
                group = files[start : start + MEDIA_GROUP_MAX]
                media = [InputMediaPhoto(f, caption=caption if start == 0 and i == 0 else None)
                         for i, f in enumerate(group)]
                await bot.send_media_group(chat_id, media)
    total = len(post.slides)
    for n, slide in enumerate(post.slides, start=1):
        if slide:
            header = i18n.t("slide_header", ui, n=n, total=total) if total > 1 else ""
            await _send_text(bot, chat_id, f"{header}\n\n{format_pairs(slide)}".strip())


async def _deliver_video(bot: Sender, chat_id: int, video: VideoReport, ui: str) -> None:
    done = i18n.t("done", ui, source=video.source_lang, target=video.target_lang)
    screen = f"{i18n.t('on_screen_header', ui)}\n{format_pairs(video.on_screen)}" if video.on_screen else ""
    if video.video_path is None:  # no speech: only the on-screen text was translated
        await _send_text(bot, chat_id, f"{done}\n\n{screen}")
        return
    if video.video_bytes > TELEGRAM_UPLOAD_LIMIT:
        raise i18n.OutputTooLargeError(f"video is {video.video_bytes} bytes")
    caption = f"{done}\n\n{screen}" if screen else done
    long_screen = len(caption) > CAPTION_LIMIT
    with video.video_path.open("rb") as f:
        # Explicit dimensions/duration: without them Telegram clients may show the
        # video small or with the wrong aspect until it loads (D-021).
        await bot.send_video(
            chat_id, f, caption=done if long_screen else caption, supports_streaming=True,
            width=video.video_width, height=video.video_height, duration=round(video.video_seconds),
        )
    if long_screen:
        await _send_text(bot, chat_id, screen)


async def process_job(
    job_id: int,
    db: Database,
    bot: Sender,
    run: PipelineRunner,
) -> bool:
    """Process one job. Returns True on success. Never raises for job failures."""
    job = db.get_job(job_id)
    user = db.get_user(job.user_id)
    db.mark_running(job_id)
    tmp = Path(tempfile.mkdtemp(prefix="reel-"))
    try:
        result: JobResult = await asyncio.to_thread(
            run, job.url, job.target_lang, name=f"reel-{job_id}",
            work_dir=tmp / "work", out_dir=tmp / "out",
        )
        if result.image_post:
            await _deliver_images(bot, job.user_id, result.image_post, user.ui_lang)
        for video in result.videos:
            await _deliver_video(bot, job.user_id, video, user.ui_lang)
        first = result.image_post or result.videos[0]
        audio = sum(v.audio_seconds for v in result.videos)
        db.mark_done(job_id, first.source_lang, audio)
        return True
    except Exception as exc:  # every failure must reach the user
        log.warning("job %s failed: %s: %s", job_id, type(exc).__name__, exc)
        db.mark_failed(job_id, f"{type(exc).__name__}: {exc}")
        try:
            await bot.send_message(job.user_id, i18n.t(i18n.error_key(exc), user.ui_lang))
        except Exception:
            log.exception("could not notify user of failed job %s", job_id)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if tmp.exists():
            log.error("job %s: temporary files could not be deleted: %s", job_id, tmp)


def make_runner(source, stt, translator, ocr) -> PipelineRunner:
    """Bind the core providers once; the adapter only passes job parameters."""
    def run(url: str, target_lang: str, *, name: str, work_dir: Path, out_dir: Path) -> JobResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        return pipeline.run_job(
            url, target_lang, name=name, work_dir=work_dir, out_dir=out_dir,
            source=source, stt=stt, translator=translator, ocr=ocr,
        )
    return run
