"""SQLite storage for users and jobs (ARCHITECTURE → Data model)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id    INTEGER PRIMARY KEY,
    target_lang    TEXT,
    ui_lang        TEXT NOT NULL DEFAULT 'en',
    ui_lang_chosen INTEGER NOT NULL DEFAULT 0,
    is_whitelisted INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(telegram_id),
    url         TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    error       TEXT,
    source_lang TEXT,
    duration_s  REAL,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class User:
    telegram_id: int
    target_lang: str | None
    ui_lang: str
    ui_lang_chosen: bool  # False until the user picks the bot language explicitly
    is_whitelisted: bool


@dataclass
class Job:
    id: int
    user_id: int
    url: str
    target_lang: str
    status: str


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(users)")}
        if "ui_lang_chosen" not in columns:
            with self._conn:
                self._conn.execute("ALTER TABLE users ADD COLUMN ui_lang_chosen INTEGER NOT NULL DEFAULT 0")

    def close(self) -> None:
        self._conn.close()

    # Users
    def upsert_user(self, telegram_id: int, default_ui_lang: str, is_whitelisted: bool) -> User:
        """The Telegram client language is only a default until the user chooses one."""
        with self._conn:
            self._conn.execute(
                """INSERT INTO users (telegram_id, ui_lang, is_whitelisted, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                     ui_lang = CASE WHEN users.ui_lang_chosen THEN users.ui_lang ELSE excluded.ui_lang END,
                     is_whitelisted = excluded.is_whitelisted""",
                (telegram_id, default_ui_lang, int(is_whitelisted), _now()),
            )
        return self.get_user(telegram_id)

    def get_user(self, telegram_id: int) -> User:
        row = self._conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        return User(row["telegram_id"], row["target_lang"], row["ui_lang"],
                    bool(row["ui_lang_chosen"]), bool(row["is_whitelisted"]))

    def set_ui_lang(self, telegram_id: int, lang: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE users SET ui_lang = ?, ui_lang_chosen = 1 WHERE telegram_id = ?", (lang, telegram_id)
            )

    def set_target_lang(self, telegram_id: int, lang: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE users SET target_lang = ? WHERE telegram_id = ?", (lang, telegram_id))

    # Jobs
    def create_job(self, user_id: int, url: str, target_lang: str) -> Job:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO jobs (user_id, url, target_lang, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
                (user_id, url, target_lang, _now()),
            )
        return Job(cur.lastrowid, user_id, url, target_lang, "queued")

    def get_job(self, job_id: int) -> Job:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job(row["id"], row["user_id"], row["url"], row["target_lang"], row["status"])

    def mark_running(self, job_id: int) -> None:
        with self._conn:
            self._conn.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,))

    def mark_done(self, job_id: int, source_lang: str, duration_s: float) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET status = 'done', source_lang = ?, duration_s = ?, finished_at = ? WHERE id = ?",
                (source_lang, duration_s, _now(), job_id),
            )

    def mark_failed(self, job_id: int, error: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                (error, _now(), job_id),
            )

    def unfinished_jobs(self) -> list[Job]:
        rows = self._conn.execute("SELECT * FROM jobs WHERE status IN ('queued', 'running') ORDER BY id").fetchall()
        return [Job(r["id"], r["user_id"], r["url"], r["target_lang"], r["status"]) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
