import sqlite3
from datetime import datetime, timezone

from storage import USERS_DATABASE


def initialize_users() -> None:
    with sqlite3.connect(USERS_DATABASE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                language TEXT NOT NULL CHECK (language IN ('ru', 'en')),
                registered_at TEXT NOT NULL
            )
        """)


def save_user(telegram_id: int, username: str | None, first_name: str, last_name: str | None, initial_language: str) -> str:
    with sqlite3.connect(USERS_DATABASE) as connection:
        row = connection.execute("SELECT language FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name, initial_language, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            return initial_language
        connection.execute(
            "UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE telegram_id = ?",
            (username, first_name, last_name, telegram_id),
        )
        return str(row[0])


def set_user_language(telegram_id: int, language: str) -> None:
    with sqlite3.connect(USERS_DATABASE) as connection:
        connection.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (language, telegram_id))
