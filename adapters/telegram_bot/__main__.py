"""Run the bot: python -m adapters.telegram_bot"""

import logging

from dotenv import load_dotenv

from adapters.telegram_bot import config
from adapters.telegram_bot.bot import build_application

load_dotenv()
logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # do not log request URLs (they contain the token)

build_application(config.load()).run_polling()
