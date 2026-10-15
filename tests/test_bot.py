import asyncio
from pathlib import Path

import pytest

from adapters.telegram_bot import i18n
from adapters.telegram_bot.db import Database
from adapters.telegram_bot.jobs import TELEGRAM_UPLOAD_LIMIT, chunks, process_job
from core.errors import FetchError, NoSpeechError, NoTextError, OcrError, TranslationMismatchError
from core.pipeline import ImagePostReport, JobResult, TextPair, VideoReport


class FakeBot:
    def __init__(self):
        self.messages, self.videos, self.documents, self.photos, self.groups = [], [], [], [], []

    async def send_photo(self, chat_id, photo, **kwargs):
        self.photos.append((chat_id, photo.read(), kwargs))

    async def send_media_group(self, chat_id, media, **kwargs):
        self.groups.append((chat_id, [(m.media, m.caption) for m in media]))

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


def ok_runner(video_bytes=10, on_screen=None):
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
        return JobResult(videos=[VideoReport(
            video_path=video, source_lang="es", target_lang=target_lang, on_screen=on_screen or [],
            transcript_path=out_dir / "t.json", srt_path=out_dir / "t.srt", study_path=study,
            video_bytes=video_bytes, video_width=720, video_height=1280, video_seconds=5.4,
            segments=1, cues=1, audio_seconds=5.0, llm_tokens=10, llm_model="m", word_timestamps=True,
        )])

    return run, seen


def failing_runner(exc):
    seen = {}

    def run(url, target_lang, *, name, work_dir, out_dir):
        work_dir.mkdir(parents=True)
        (work_dir / "video.mp4").write_bytes(b"partial")
        seen["root"] = work_dir.parent
        raise exc

    return run, seen


def test_success_sends_only_the_video_and_cleans_up(db):
    bot, (run, seen) = FakeBot(), ok_runner()
    job_id = _job(db)
    assert asyncio.run(process_job(job_id, db, bot, run)) is True
    assert bot.videos[0][0] == 7 and "es → en" in bot.videos[0][2]["caption"]
    assert (bot.videos[0][2]["width"], bot.videos[0][2]["height"], bot.videos[0][2]["duration"]) == (720, 1280, 5)
    assert bot.documents == []  # the study transcript is not sent by the bot (D-019)
    assert db.get_job(job_id).status == "done"
    assert not seen["root"].exists()


@pytest.mark.parametrize("exc, key", [
    (FetchError("x"), "err_fetch"),
    (NoSpeechError("x"), "err_no_speech"),
    (TranslationMismatchError("x"), "err_translation"),
    (NoTextError("x"), "err_no_text"),
    (OcrError("x"), "err_ocr"),
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


def test_every_message_formats_with_its_handler_arguments():
    args = {"language": "English", "user_id": 1, "position": 1, "source": "es", "target": "en", "n": 1, "total": 2}
    for key in i18n.MESSAGES:
        for ui in i18n.UI_LANGS:
            assert "{" not in i18n.t(key, ui, **args), (key, ui)


def test_chosen_bot_language_survives_telegram_language(db):
    db.upsert_user(9, "ru", True)          # first contact: default from Telegram
    assert db.get_user(9).ui_lang == "ru" and not db.get_user(9).ui_lang_chosen
    db.set_ui_lang(9, "es")
    assert db.upsert_user(9, "ru", True).ui_lang == "es"  # explicit choice wins


def test_unchosen_bot_language_follows_telegram(db):
    db.upsert_user(10, "en", True)
    assert db.upsert_user(10, "ru", True).ui_lang == "ru"


def test_menu_buttons_recognized_in_any_language():
    for ui in i18n.UI_LANGS:
        assert i18n.button_action(i18n.t("btn_ui", ui)) == "btn_ui"
        assert i18n.button_action(i18n.t("btn_target", ui)) == "btn_target"
        assert i18n.button_action(i18n.t("btn_help", ui)) == "btn_help"
    assert i18n.button_action("https://www.instagram.com/reel/x/") is None


def test_old_database_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, target_lang TEXT, "
                 "ui_lang TEXT NOT NULL DEFAULT 'en', is_whitelisted INTEGER NOT NULL DEFAULT 0, "
                 "created_at TEXT NOT NULL)")
    conn.execute("INSERT INTO users VALUES (1, 'ru', 'es', 1, 'x')")
    conn.commit()
    conn.close()
    d = Database(path)
    assert d.get_user(1).ui_lang_chosen is False and d.get_user(1).target_lang == "ru"
    d.close()


def image_runner(n_images, slides):
    seen = {}

    def run(url, target_lang, *, name, work_dir, out_dir):
        work_dir.mkdir(parents=True)
        images = []
        for i in range(n_images):
            p = work_dir / f"{i:03}.jpg"
            p.write_bytes(f"img{i}".encode())
            images.append(p)
        seen["root"] = work_dir.parent
        return JobResult(image_post=ImagePostReport(images=images, slides=slides, source_lang="en",
                                                    target_lang=target_lang))

    return run, seen


def test_carousel_sends_album_and_one_message_per_slide_with_text(db):
    slides = [[TextPair("Pick one", "Elige uno")], [], [TextPair("A) Yes", "A) Sí"), TextPair("B) No", "B) No")]]
    bot, (run, seen) = FakeBot(), image_runner(3, slides)
    assert asyncio.run(process_job(_job(db), db, bot, run)) is True
    (chat, media), = bot.groups
    assert chat == 7 and len(media) == 3
    assert "en → en" in media[0][1] and media[1][1] is None
    assert [m[1] for m in bot.messages] == [
        i18n.t("slide_header", "es", n=1, total=3) + "\n\nPick one\n➜ Elige uno",
        i18n.t("slide_header", "es", n=3, total=3) + "\n\nA) Yes\n➜ A) Sí\n\nB) No\n➜ B) No",
    ]
    assert not seen["root"].exists()


def test_single_image_is_sent_as_photo_without_slide_header(db):
    bot, (run, _) = FakeBot(), image_runner(1, [[TextPair("Hello", "Hola")]])
    assert asyncio.run(process_job(_job(db), db, bot, run)) is True
    assert bot.photos[0][1] == b"img0" and bot.groups == []
    assert bot.messages == [(7, "Hello\n➜ Hola")]


def test_on_screen_text_goes_in_video_caption(db):
    bot, (run, _) = FakeBot(), ok_runner(on_screen=[TextPair("Cuando convivimos", "When we live together")])
    assert asyncio.run(process_job(_job(db), db, bot, run)) is True
    caption = bot.videos[0][2]["caption"]
    assert i18n.t("on_screen_header", "es") in caption
    assert "Cuando convivimos\n➜ When we live together" in caption


def test_video_without_speech_sends_only_on_screen_text(db):
    def run(url, target_lang, *, name, work_dir, out_dir):
        return JobResult(videos=[VideoReport(video_path=None, source_lang="es", target_lang=target_lang,
                                             on_screen=[TextPair("Hola", "Hello")])])
    bot = FakeBot()
    assert asyncio.run(process_job(_job(db), db, bot, run)) is True
    assert bot.videos == [] and "Hola\n➜ Hello" in bot.messages[0][1]


def test_long_text_is_chunked_on_paragraphs():
    text = "\n\n".join(["x" * 1500] * 5)
    pieces = chunks(text)
    assert all(len(piece) <= 4000 for piece in pieces) and "\n\n".join(pieces) == text
