"""Telegram handlers and the asyncio worker (D-009). No pipeline logic here (D-007)."""

from __future__ import annotations

import asyncio
import logging
import re

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
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


def _menu(ui: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[i18n.t("btn_target", ui), i18n.t("btn_ui", ui)], [i18n.t("btn_help", ui)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def _lang_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.LANG_LABELS[code], callback_data=f"{prefix}:{code}")] for code in SUPPORTED_LANGS]
    )


async def _send_next_step(bot, chat_id: int, user: User) -> None:
    """Onboarding: bot language first, then translation language, then the menu."""
    if not user.ui_lang_chosen:
        await bot.send_message(chat_id, i18n.CHOOSE_UI_PROMPT, reply_markup=_lang_keyboard("ui"))
    elif not user.target_lang:
        await bot.send_message(chat_id, i18n.t("choose_lang", user.ui_lang), reply_markup=_lang_keyboard("lang"))
    else:
        await bot.send_message(chat_id, i18n.t("menu_ready", user.ui_lang), reply_markup=_menu(user.ui_lang))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if not user:
        return
    if user.ui_lang_chosen:
        await update.effective_message.reply_text(i18n.t("start", user.ui_lang))
    await _send_next_step(context.bot, update.effective_chat.id, user)


async def ask_target_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if user:
        await update.effective_message.reply_text(
            i18n.t("choose_lang", user.ui_lang), reply_markup=_lang_keyboard("lang")
        )


async def ask_ui_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if user:
        await update.effective_message.reply_text(i18n.CHOOSE_UI_PROMPT, reply_markup=_lang_keyboard("ui"))


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _allowed(update, _state(context))
    if user:
        await update.effective_message.reply_text(i18n.t("help", user.ui_lang), reply_markup=_menu(user.ui_lang))


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for both language keyboards: `ui:<code>` (bot) and `lang:<code>` (translation)."""
    state = _state(context)
    query = update.callback_query
    await query.answer()
    user = await _allowed(update, state)
    if not user:
        return
    kind, code = query.data.split(":", 1)
    if code not in SUPPORTED_LANGS:
        return
    first_time = not user.ui_lang_chosen
    if kind == "ui":
        state.db.set_ui_lang(user.telegram_id, code)
        user = state.db.get_user(user.telegram_id)
        await query.edit_message_text(i18n.t("ui_set", user.ui_lang))
        if first_time:
            await context.bot.send_message(update.effective_chat.id, i18n.t("start", user.ui_lang))
    else:
        state.db.set_target_lang(user.telegram_id, code)
        user = state.db.get_user(user.telegram_id)
        await query.edit_message_text(i18n.t("lang_set", user.ui_lang, language=i18n.LANG_LABELS[code]))
    await _send_next_step(context.bot, update.effective_chat.id, user)


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    action = i18n.button_action(update.effective_message.text or "")
    if action == "btn_target":
        return await ask_target_lang(update, context)
    if action == "btn_ui":
        return await ask_ui_lang(update, context)
    if action == "btn_help":
        return await show_help(update, context)
    await link(update, context)


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
        await update.effective_message.reply_text(
            i18n.t("need_lang", user.ui_lang), reply_markup=_lang_keyboard("lang")
        )
        return
    job = state.db.create_job(user.telegram_id, match.group(0), user.target_lang)
    await state.queue.put(job.id)
    await update.effective_message.reply_text(i18n.t("queued", user.ui_lang, position=state.queue.qsize()))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unexpected handler errors are logged and the user still gets a reply."""
    log.error("handler error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        ui = i18n.ui_lang(update.effective_user.language_code if update.effective_user else None)
        if update.effective_user:
            try:
                ui = _state(context).db.get_user(update.effective_user.id).ui_lang
            except Exception:
                pass
        try:
            await context.bot.send_message(update.effective_chat.id, i18n.t("err_internal", ui))
        except Exception:
            log.exception("could not report handler error to the user")


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
    await _set_commands(app)
    state.worker = asyncio.create_task(_worker(app))


async def _set_commands(app: Application) -> None:
    """Command menu shown by Telegram, localized by the client's language."""
    names = (("start", "cmd_start"), ("idioma", "cmd_idioma"), ("idioma_bot", "cmd_idioma_bot"), ("ayuda", "cmd_ayuda"))
    try:
        for code in (None, *i18n.UI_LANGS):
            ui = code or "en"
            commands = [BotCommand(name, i18n.t(key, ui)) for name, key in names]
            await app.bot.set_my_commands(commands, language_code=code)
    except Exception:
        log.exception("could not set the command menu")


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
    app.add_handler(CommandHandler("idioma", ask_target_lang, filters=private))
    app.add_handler(CommandHandler("idioma_bot", ask_ui_lang, filters=private))
    app.add_handler(CommandHandler("ayuda", show_help, filters=private))
    app.add_handler(CallbackQueryHandler(lang_chosen, pattern=r"^(ui|lang):"))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, text_message))
    app.add_error_handler(on_error)
    return app
