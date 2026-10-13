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

MESSAGES: dict[str, dict[str, str]] = {
    "start": {
        "es": "¡Hola! Envíame el link de un reel en español, inglés o ruso y te devuelvo el video "
              "con subtítulos bilingües y la transcripción para estudiar.\n\n"
              "Primero elige a qué idioma traducir con /idioma.",
        "en": "Hi! Send me a link to a reel in Spanish, English or Russian and I'll send back the "
              "video with bilingual subtitles plus a study transcript.\n\n"
              "First choose the language to translate into with /idioma.",
        "ru": "Привет! Отправь мне ссылку на рилс на испанском, английском или русском, и я верну "
              "видео с двуязычными субтитрами и расшифровку для изучения.\n\n"
              "Сначала выбери язык перевода командой /idioma.",
    },
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
        "es": "✅ Listo ({source} → {target}). Abajo tienes la transcripción para estudiar.",
        "en": "✅ Done ({source} → {target}). The study transcript is below.",
        "ru": "✅ Готово ({source} → {target}). Ниже расшифровка для изучения.",
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
