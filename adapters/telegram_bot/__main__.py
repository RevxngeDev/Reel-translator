"""Run the bot: python -m adapters.telegram_bot

Also suitable for background use (pythonw, no console): logs go to a rotating file
and startup keeps retrying until Telegram is reachable (e.g. proxy not up yet).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from adapters.telegram_bot import config
from adapters.telegram_bot.bot import build_application

load_dotenv()

log_file = Path(os.environ.get("BOT_LOG_FILE") or "data/bot.log")
log_file.parent.mkdir(parents=True, exist_ok=True)
handlers: list[logging.Handler] = [RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")]
if sys.stderr is not None:  # None under pythonw (no console)
    handlers.append(logging.StreamHandler())
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO, handlers=handlers)
logging.getLogger("httpx").setLevel(logging.WARNING)  # do not log request URLs (they contain the token)

build_application(config.load()).run_polling(bootstrap_retries=-1)
