"""User-facing messages in es / en / ru. The UI language follows the user's Telegram
language when it is one of these, English otherwise.
"""

from __future__ import annotations

from core.errors import (
    FetchError,
    NoSpeechError,
    PipelineError,
    SameLanguageError,
    TranslationError,
    UnsupportedLanguageError,
)

UI_LANGS = ("es", "en", "ru")

LANG_LABELS = {"es": "🇪🇸 Español", "en": "🇬🇧 English", "ru": "🇷🇺 Русский"}

# Shown before the user has chosen a bot language, so it is in all three at once.
CHOOSE_UI_PROMPT = "🗣 Elige el idioma del bot · Choose the bot language · Выбери язык бота"

MESSAGES: dict[str, dict[str, str]] = {
    "start": {
        "es": "¡Hola! Envíame el link de un reel en español, inglés o ruso y te devuelvo el video "
              "con subtítulos bilingües: el original arriba y la traducción abajo.",
        "en": "Hi! Send me a link to a reel in Spanish, English or Russian and I'll send back the "
              "video with bilingual subtitles: the original on top, the translation below.",
        "ru": "Привет! Отправь мне ссылку на рилс на испанском, английском или русском, и я верну "
              "видео с двуязычными субтитрами: оригинал сверху, перевод снизу.",
    },
    "help": {
        "es": "Cómo usarme:\n"
              "1. Envíame el link de un reel (Instagram u otra red).\n"
              "2. Espera unos segundos: te devuelvo el video subtitulado.\n\n"
              "🎯 Idioma de traducción: a qué idioma traduzco los videos.\n"
              "🗣 Idioma del bot: en qué idioma te hablo yo.",
        "en": "How to use me:\n"
              "1. Send me a reel link (Instagram or another network).\n"
              "2. Wait a few seconds: I'll send back the subtitled video.\n\n"
              "🎯 Translation language: the language I translate videos into.\n"
              "🗣 Bot language: the language I talk to you in.",
        "ru": "Как мной пользоваться:\n"
              "1. Отправь ссылку на рилс (Instagram или другая сеть).\n"
              "2. Подожди немного — я пришлю видео с субтитрами.\n\n"
              "🎯 Язык перевода: на какой язык я перевожу видео.\n"
              "🗣 Язык бота: на каком языке я с тобой общаюсь.",
    },
    "ui_set": {
        "es": "✅ Te hablaré en español.",
        "en": "✅ I'll talk to you in English.",
        "ru": "✅ Буду общаться с тобой на русском.",
    },
    "menu_ready": {
        "es": "Todo listo. Envíame el link de un reel cuando quieras.",
        "en": "All set. Send me a reel link whenever you like.",
        "ru": "Всё готово. Присылай ссылку на рилс, когда захочешь.",
    },
    "btn_target": {"es": "🎯 Idioma de traducción", "en": "🎯 Translation language", "ru": "🎯 Язык перевода"},
    "btn_ui": {"es": "🗣 Idioma del bot", "en": "🗣 Bot language", "ru": "🗣 Язык бота"},
    "btn_help": {"es": "❓ Ayuda", "en": "❓ Help", "ru": "❓ Помощь"},
    "cmd_start": {"es": "Empezar", "en": "Start", "ru": "Начать"},
    "cmd_idioma": {"es": "Idioma de traducción", "en": "Translation language", "ru": "Язык перевода"},
    "cmd_idioma_bot": {"es": "Idioma del bot", "en": "Bot language", "ru": "Язык бота"},
    "cmd_ayuda": {"es": "Ayuda", "en": "Help", "ru": "Помощь"},
    "choose_lang": {
        "es": "¿A qué idioma quieres traducir los videos?",
        "en": "Which language should I translate videos into?",
        "ru": "На какой язык переводить видео?",
    },
    "lang_set": {
        "es": "Listo: traduciré a {language}. Ahora envíame el link de un reel.",
        "en": "Done: I'll translate into {language}. Now send me a reel link.",
        "ru": "Готово: буду переводить на {language}. Теперь отправь ссылку на рилс.",
    },
    "need_lang": {
        "es": "Primero elige el idioma de traducción con /idioma.",
        "en": "First choose the translation language with /idioma.",
        "ru": "Сначала выбери язык перевода командой /idioma.",
    },
    "not_whitelisted": {
        "es": "Este bot es privado por ahora. Tu ID de Telegram es {user_id}.",
        "en": "This bot is private for now. Your Telegram ID is {user_id}.",
        "ru": "Пока этот бот закрытый. Твой Telegram ID: {user_id}.",
    },
    "not_a_link": {
        "es": "Envíame el link de un reel (por ejemplo, https://www.instagram.com/reel/...).",
        "en": "Send me a reel link (for example, https://www.instagram.com/reel/...).",
        "ru": "Отправь ссылку на рилс (например, https://www.instagram.com/reel/...).",
    },
    "queued": {
        "es": "⏳ Recibido. Procesando… (posición en la cola: {position})",
        "en": "⏳ Got it. Processing… (queue position: {position})",
        "ru": "⏳ Принято. Обрабатываю… (место в очереди: {position})",
    },
    "done": {
        "es": "✅ Listo ({source} → {target}).",
        "en": "✅ Done ({source} → {target}).",
        "ru": "✅ Готово ({source} → {target}).",
    },
    "err_fetch": {
        "es": "❌ No pude descargar ese video. Revisa que el link sea correcto y el reel sea público.",
        "en": "❌ I couldn't download that video. Check the link is correct and the reel is public.",
        "ru": "❌ Не удалось скачать видео. Проверь ссылку и что рилс открыт для всех.",
    },
    "err_unsupported_lang": {
        "es": "❌ El video no está en español, inglés ni ruso, los únicos idiomas que entiendo.",
        "en": "❌ The video isn't in Spanish, English or Russian, the only languages I support.",
        "ru": "❌ Видео не на испанском, английском или русском — других языков я не знаю.",
    },
    "err_same_lang": {
        "es": "❌ El video ya está en el idioma al que traduces. Cámbialo con /idioma.",
        "en": "❌ The video is already in your target language. Change it with /idioma.",
        "ru": "❌ Видео уже на языке перевода. Поменяй его командой /idioma.",
    },
    "err_no_speech": {
        "es": "❌ No encontré voz en el video, así que no hay nada que traducir.",
        "en": "❌ I found no speech in the video, so there's nothing to translate.",
        "ru": "❌ В видео нет речи, поэтому переводить нечего.",
    },
    "err_translation": {
        "es": "❌ Falló la traducción. Inténtalo de nuevo en unos minutos.",
        "en": "❌ Translation failed. Please try again in a few minutes.",
        "ru": "❌ Перевод не удался. Попробуй ещё раз через несколько минут.",
    },
    "err_too_big": {
        "es": "❌ El video subtitulado pesa más de 50 MB, el máximo que Telegram me deja enviar.",
        "en": "❌ The subtitled video is over 50 MB, the most Telegram lets me send.",
        "ru": "❌ Видео с субтитрами больше 50 МБ — это максимум, который разрешает Telegram.",
    },
    "err_internal": {
        "es": "❌ Algo salió mal procesando tu video. Inténtalo de nuevo.",
        "en": "❌ Something went wrong while processing your video. Please try again.",
        "ru": "❌ Что-то пошло не так при обработке видео. Попробуй ещё раз.",
    },
    "interrupted": {
        "es": "❌ Tu video no se terminó de procesar porque el bot se reinició. Envía el link otra vez.",
        "en": "❌ Your video wasn't finished because the bot restarted. Please send the link again.",
        "ru": "❌ Видео не обработано, потому что бот перезапустился. Отправь ссылку ещё раз.",
    },
}


def ui_lang(telegram_language_code: str | None) -> str:
    code = (telegram_language_code or "").split("-")[0].lower()
    return code if code in UI_LANGS else "en"


def t(key: str, ui: str, /, **kwargs: object) -> str:
    return MESSAGES[key][ui].format(**kwargs)


def button_action(text: str) -> str | None:
    """Which menu button a text is, in any language (the user may have switched)."""
    for key in ("btn_target", "btn_ui", "btn_help"):
        if text in MESSAGES[key].values():
            return key
    return None


class OutputTooLargeError(PipelineError):
    """The rendered video exceeds Telegram's bot upload limit."""


def error_key(exc: BaseException) -> str:
    """Map a job failure to the message the user receives."""
    if isinstance(exc, OutputTooLargeError):
        return "err_too_big"
    if isinstance(exc, FetchError):
        return "err_fetch"
    if isinstance(exc, UnsupportedLanguageError):
        return "err_unsupported_lang"
    if isinstance(exc, SameLanguageError):
        return "err_same_lang"
    if isinstance(exc, NoSpeechError):
        return "err_no_speech"
    if isinstance(exc, TranslationError):
        return "err_translation"
    return "err_internal"
