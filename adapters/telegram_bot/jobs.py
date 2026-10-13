"""Runs one queued job: pipeline in a worker thread, delivery of the subtitled video
(D-019), and guaranteed cleanup.

Every job ends with a message to the user (Phase 2 gate) and with no video or audio
left on disk: all job files live in one temporary directory removed at the end.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from adapters.telegram_bot import i18n
from adapters.telegram_bot.db import Database
from core import pipeline

log = logging.getLogger(__name__)

TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024  # standard Bot API upload limit (D-006/D-010)


class Sender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> object: ...
    async def send_video(self, chat_id: int, video: object, **kwargs: object) -> object: ...


PipelineRunner = Callable[..., pipeline.JobReport]


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
    message: str
    try:
        report = await asyncio.to_thread(
            run, job.url, job.target_lang, name=f"reel-{job_id}",
            work_dir=tmp / "work", out_dir=tmp / "out",
        )
        if report.video_path is None or report.video_bytes > TELEGRAM_UPLOAD_LIMIT:
            raise i18n.OutputTooLargeError(f"video is {report.video_bytes} bytes")
        caption = i18n.t("done", user.ui_lang, source=report.source_lang, target=report.target_lang)
        with report.video_path.open("rb") as video:
            await bot.send_video(job.user_id, video, caption=caption, supports_streaming=True)
        db.mark_done(job_id, report.source_lang, report.audio_seconds)
        return True
    except Exception as exc:  # every failure must reach the user
        log.warning("job %s failed: %s: %s", job_id, type(exc).__name__, exc)
        db.mark_failed(job_id, f"{type(exc).__name__}: {exc}")
        message = i18n.t(i18n.error_key(exc), user.ui_lang)
        try:
            await bot.send_message(job.user_id, message)
        except Exception:
            log.exception("could not notify user of failed job %s", job_id)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if tmp.exists():
            log.error("job %s: temporary files could not be deleted: %s", job_id, tmp)


def make_runner(source, stt, translator) -> PipelineRunner:
    """Bind the core providers once; the adapter only passes job parameters."""
    def run(url: str, target_lang: str, *, name: str, work_dir: Path, out_dir: Path) -> pipeline.JobReport:
        work_dir.mkdir(parents=True, exist_ok=True)
        return pipeline.run_job(
            url, target_lang, name=name, work_dir=work_dir, out_dir=out_dir,
            source=source, stt=stt, translator=translator,
        )
    return run
