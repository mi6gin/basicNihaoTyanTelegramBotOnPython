import sqlite3
from datetime import datetime, timezone

from storage import APPEALS_DATABASE
from storage.models import Appeal


def initialize_appeals() -> None:
    with sqlite3.connect(APPEALS_DATABASE) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                status INTEGER NOT NULL DEFAULT 0 CHECK (status IN (0, 1)),
                answer TEXT,
                created_at TEXT NOT NULL,
                answered_at TEXT
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS appeals_user_id_id ON appeals(user_id, id DESC)")


def create_appeal(user_id: int, appeal_text: str) -> int:
    with sqlite3.connect(APPEALS_DATABASE) as connection:
        cursor = connection.execute(
            "INSERT INTO appeals(user_id, text, created_at) VALUES (?, ?, ?)",
            (user_id, appeal_text, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)


def get_appeal_at(user_id: int, offset: int) -> tuple[Appeal | None, int]:
    with sqlite3.connect(APPEALS_DATABASE) as connection:
        count = int(connection.execute("SELECT COUNT(*) FROM appeals WHERE user_id = ?", (user_id,)).fetchone()[0])
        row = connection.execute(
            "SELECT id, user_id, text, status, answer, created_at FROM appeals WHERE user_id = ? ORDER BY id DESC LIMIT 1 OFFSET ?",
            (user_id, max(offset, 0)),
        ).fetchone()
    return (Appeal(*row) if row else None, count)


def get_appeal(user_id: int, appeal_id: int) -> Appeal | None:
    with sqlite3.connect(APPEALS_DATABASE) as connection:
        row = connection.execute(
            "SELECT id, user_id, text, status, answer, created_at FROM appeals WHERE user_id = ? AND id = ?",
            (user_id, appeal_id),
        ).fetchone()
    return Appeal(*row) if row else None


def get_appeal_offset(user_id: int, appeal_id: int) -> int | None:
    with sqlite3.connect(APPEALS_DATABASE) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM appeals WHERE user_id = ? AND id > ?",
            (user_id, appeal_id),
        ).fetchone()
        exists = connection.execute(
            "SELECT 1 FROM appeals WHERE user_id = ? AND id = ?",
            (user_id, appeal_id),
        ).fetchone()
    return int(row[0]) if exists else None
