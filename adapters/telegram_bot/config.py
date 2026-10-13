from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str
    whitelist: frozenset[int]
    db_path: Path
    proxy: str | None  # e.g. http://127.0.0.1:12334 where Telegram is blocked


def _parse_ids(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x)


def load() -> Config:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    return Config(
        token=token,
        whitelist=_parse_ids(os.environ.get("TELEGRAM_WHITELIST", "")),
        db_path=Path(os.environ.get("BOT_DB_PATH") or "data/bot.sqlite3"),
        proxy=os.environ.get("TELEGRAM_PROXY") or None,
    )
