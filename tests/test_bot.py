import asyncio
from pathlib import Path

import pytest

from adapters.telegram_bot import i18n
from adapters.telegram_bot.db import Database
from adapters.telegram_bot.jobs import TELEGRAM_UPLOAD_LIMIT, process_job
from core.errors import FetchError, NoSpeechError, TranslationMismatchError
from core.pipeline import JobReport


class FakeBot:
    def __init__(self):
        self.messages, self.videos, self.documents = [], [], []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))

    async def send_video(self, chat_id, video, **kwargs):
        self.videos.append((chat_id, video.read(), kwargs))

    async def send_document(self, chat_id, document, **kwargs):
        self.documents.append((chat_id, document.read(), kwargs))


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "bot.sqlite3")
    d.upsert_user(7, "es", True)
    d.set_target_lang(7, "en")
    yield d
    d.close()


def _job(db):
    return db.create_job(7, "https://example.invalid/reel", "en").id


def ok_runner(video_bytes=10):
    seen = {}

    def run(url, target_lang, *, name, work_dir, out_dir):
        out_dir.mkdir(parents=True)
        work_dir.mkdir(parents=True)
        (work_dir / "video.mp4").write_bytes(b"source video")
        (work_dir / "audio.flac").write_bytes(b"audio")
        video = out_dir / f"{name}.mp4"
        video.write_bytes(b"x" * 10)
        study = out_dir / f"{name}.txt"
        study.write_bytes("Hola\n  Hello".encode())
        seen["root"] = work_dir.parent
        return JobReport(
            transcript_path=out_dir / "t.json", srt_path=out_dir / "t.srt", study_path=study,
            video_path=video, video_bytes=video_bytes, source_lang="es", target_lang=target_lang,
            segments=1, cues=1, layout_violations=[], audio_seconds=5.0, llm_tokens=10,
            llm_model="m", word_timestamps=True,
        )

    return run, seen


def failing_runner(exc):
    seen = {}

    def run(url, target_lang, *, name, work_dir, out_dir):
        work_dir.mkdir(parents=True)
        (work_dir / "video.mp4").write_bytes(b"partial")
        seen["root"] = work_dir.parent
        raise exc

    return run, seen


def test_success_sends_video_and_transcript_and_cleans_up(db):
    bot, (run, seen) = FakeBot(), ok_runner()
    job_id = _job(db)
    assert asyncio.run(process_job(job_id, db, bot, run)) is True
    assert bot.videos[0][0] == 7 and "es → en" in bot.videos[0][2]["caption"]
    assert bot.documents[0][1] == "Hola\n  Hello".encode()
    assert db.get_job(job_id).status == "done"
    assert not seen["root"].exists()


@pytest.mark.parametrize("exc, key", [
    (FetchError("x"), "err_fetch"),
    (NoSpeechError("x"), "err_no_speech"),
    (TranslationMismatchError("x"), "err_translation"),
    (RuntimeError("bug"), "err_internal"),
])
def test_every_failure_notifies_user_and_cleans_up(db, exc, key):
    bot, (run, seen) = FakeBot(), failing_runner(exc)
    job_id = _job(db)
    assert asyncio.run(process_job(job_id, db, bot, run)) is False
    assert bot.messages == [(7, i18n.t(key, "es"))]
    assert db.get_job(job_id).status == "failed"
    assert not seen["root"].exists()


def test_oversized_video_is_reported(db):
    bot, (run, seen) = FakeBot(), ok_runner(video_bytes=TELEGRAM_UPLOAD_LIMIT + 1)
    assert asyncio.run(process_job(_job(db), db, bot, run)) is False
    assert bot.videos == [] and bot.messages == [(7, i18n.t("err_too_big", "es"))]
    assert not seen["root"].exists()


def test_unfinished_jobs_listed_for_restart_recovery(db):
    a, b = _job(db), _job(db)
    db.mark_running(a)
    db.mark_done(b, "es", 1.0)
    assert [j.id for j in db.unfinished_jobs()] == [a]


def test_whitelist_flag_follows_config(db):
    assert db.upsert_user(8, "ru", False).is_whitelisted is False
    assert db.upsert_user(8, "ru", True).is_whitelisted is True


def test_all_messages_exist_in_three_languages():
    for key, texts in i18n.MESSAGES.items():
        assert set(texts) == set(i18n.UI_LANGS), key


def test_ui_lang_fallback():
    assert i18n.ui_lang("es-419") == "es"
    assert i18n.ui_lang("ru") == "ru"
    assert i18n.ui_lang("de") == "en"
    assert i18n.ui_lang(None) == "en"
