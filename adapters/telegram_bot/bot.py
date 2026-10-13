"""Telegram handlers and the asyncio worker (D-009). No pipeline logic here (D-007)."""

from __future__ import annotations

import asyncio
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from adapters.telegram_bot import i18n
from adapters.telegram_bot.config import Config
from adapters.telegram_bot.db import Database, User
from adapters.telegram_bot.jobs import make_runner, process_job
from core import SUPPORTED_LANGS, providers

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")


class BotState:
    def __init__(self, config: Config, db: Database) -> None:
        self.config = config
        self.db = db
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.runner = make_runner(providers.video_source(), providers.speech_to_text(), providers.translator())
        self.worker: asyncio.Task | None = None


def _state(context: ContextTypes.DEFAULT_TYPE) -> BotState:
    return context.application.bot_data["state"]


def _register(update: Update, state: BotState) -> User:
    tg_user = update.effective_user
    return state.db.upsert_user(
        tg_user.id,
        i18n.ui_lang(tg_user.language_code),
        tg_user.id in state.config.whitelist,
    )


async def _allowed(update: Update, state: BotState) -> User | None:
    user = _register(update, state)
    if not user.is_whitelisted:
        log.info("rejected non-whitelisted user %s", user.telegram_id)
        await update.effective_message.reply_text(
            i18n.t("not_whitelisted", user.ui_lang, user_id=user.telegram_id)
        )
        return None
    return user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if user:
        await update.effective_message.reply_text(i18n.t("start", user.ui_lang))


async def idioma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if not user:
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.LANG_LABELS[code], callback_data=f"lang:{code}")] for code in SUPPORTED_LANGS]
    )
    await update.effective_message.reply_text(i18n.t("choose_lang", user.ui_lang), reply_markup=keyboard)


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _state(context)
    query = update.callback_query
    await query.answer()
    user = await _allowed(update, state)
    if not user:
        return
    code = query.data.split(":", 1)[1]
    if code not in SUPPORTED_LANGS:
        return
    state.db.set_target_lang(user.telegram_id, code)
    await query.edit_message_text(i18n.t("lang_set", user.ui_lang, lang=i18n.LANG_LABELS[code]))


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = _state(context)
    user = await _allowed(update, state)
    if not user:
        return
    match = URL_RE.search(update.effective_message.text or "")
    if not match:
        await update.effective_message.reply_text(i18n.t("not_a_link", user.ui_lang))
        return
    if not user.target_lang:
        await update.effective_message.reply_text(i18n.t("need_lang", user.ui_lang))
        return
    job = state.db.create_job(user.telegram_id, match.group(0), user.target_lang)
    await state.queue.put(job.id)
    await update.effective_message.reply_text(i18n.t("queued", user.ui_lang, position=state.queue.qsize()))


async def _worker(app: Application) -> None:
    state: BotState = app.bot_data["state"]
    while True:
        job_id = await state.queue.get()
        try:
            await process_job(job_id, state.db, app.bot, state.runner)
        except Exception:
            log.exception("worker error on job %s", job_id)
        finally:
            state.queue.task_done()


async def _post_init(app: Application) -> None:
    state: BotState = app.bot_data["state"]
    # Jobs left unfinished by a previous run are failed and reported (Phase 2 gate).
    for job in state.db.unfinished_jobs():
        state.db.mark_failed(job.id, "interrupted by restart")
        user = state.db.get_user(job.user_id)
        try:
            await app.bot.send_message(job.user_id, i18n.t("interrupted", user.ui_lang))
        except Exception:
            log.exception("could not notify user of interrupted job %s", job.id)
    state.worker = asyncio.create_task(_worker(app))


async def _post_shutdown(app: Application) -> None:
    state: BotState = app.bot_data["state"]
    if state.worker:
        state.worker.cancel()
    state.db.close()


def build_application(config: Config) -> Application:
    builder = (
        ApplicationBuilder()
        .token(config.token)
        .connect_timeout(30)
        .read_timeout(30)
        .get_updates_connect_timeout(30)
        .media_write_timeout(120)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
    )
    if config.proxy:
        builder = builder.proxy(config.proxy).get_updates_proxy(config.proxy)
    app = builder.build()
    app.bot_data["state"] = BotState(config, Database(config.db_path))
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", start, filters=private))
    app.add_handler(CommandHandler("idioma", idioma, filters=private))
    app.add_handler(CallbackQueryHandler(lang_chosen, pattern=r"^lang:"))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, link))
    return app
