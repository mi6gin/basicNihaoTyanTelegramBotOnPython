"""One-time import of the bot's legacy SQLite databases into PostgreSQL."""

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from settings import settings
from storage import APPEALS_DATABASE, USERS_DATABASE, create_database_engine
from storage.tables import appeal_messages, appeals, bot_chats, data_imports, fsm_states, users

IMPORT_NAME = "legacy-sqlite-v1"


def _rows(path: Path, table: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')] if exists else []


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


async def import_sqlite() -> bool:
    if not USERS_DATABASE.is_file() and not APPEALS_DATABASE.is_file():
        print("SQLite import skipped: no legacy databases found")
        return False

    engine = create_database_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            if await connection.scalar(select(data_imports.c.name).where(data_imports.c.name == IMPORT_NAME)):
                print("SQLite import already completed")
                return False

            user_rows = _rows(USERS_DATABASE, "users")
            appeal_rows = _rows(APPEALS_DATABASE, "appeals")
            known_user_ids = {int(row["telegram_id"]) for row in user_rows}
            for row in appeal_rows:
                user_id = int(row["user_id"])
                if user_id not in known_user_ids:
                    user_rows.append(
                        {
                            "telegram_id": user_id,
                            "username": None,
                            "first_name": "Unknown",
                            "last_name": None,
                            "language": "ru",
                            "registered_at": row.get("created_at"),
                            "last_seen_at": row.get("created_at"),
                        }
                    )
                    known_user_ids.add(user_id)

            for row in user_rows:
                registered = _datetime(row.get("registered_at")) or datetime.now(UTC)
                statement = insert(users).values(
                    telegram_id=int(row["telegram_id"]),
                    username=row.get("username"),
                    first_name=row.get("first_name") or "Unknown",
                    last_name=row.get("last_name"),
                    language=row.get("language") if row.get("language") in {"ru", "en"} else "ru",
                    registered_at=registered,
                    last_seen_at=_datetime(row.get("last_seen_at")) or registered,
                ).on_conflict_do_nothing()
                await connection.execute(statement)

            for row in _rows(USERS_DATABASE, "bot_chats"):
                first_seen = _datetime(row.get("first_seen_at")) or datetime.now(UTC)
                await connection.execute(
                    insert(bot_chats)
                    .values(
                        chat_id=int(row["chat_id"]),
                        chat_type=row.get("chat_type") or "group",
                        title=row.get("title"),
                        username=row.get("username"),
                        bot_status=row.get("bot_status") or "active",
                        first_seen_at=first_seen,
                        last_seen_at=_datetime(row.get("last_seen_at")) or first_seen,
                    )
                    .on_conflict_do_nothing()
                )

            for row in appeal_rows:
                created = _datetime(row.get("created_at")) or datetime.now(UTC)
                workflow = row.get("workflow_status") or ("closed" if row.get("status") else "new")
                await connection.execute(
                    insert(appeals)
                    .values(
                        id=int(row["id"]),
                        user_id=int(row["user_id"]),
                        text=row.get("text") or "",
                        status=bool(row.get("status")),
                        answer=row.get("answer"),
                        created_at=created,
                        answered_at=_datetime(row.get("answered_at")),
                        workflow_status=workflow,
                        updated_at=_datetime(row.get("updated_at")) or created,
                        closed_at=_datetime(row.get("closed_at")),
                        category=row.get("category") if row.get("category") in {
                            "technical", "account", "question", "suggestion", "other"
                        } else "other",
                    )
                    .on_conflict_do_nothing()
                )

            for row in _rows(APPEALS_DATABASE, "appeal_messages"):
                await connection.execute(
                    insert(appeal_messages)
                    .values(
                        id=int(row["id"]),
                        appeal_id=int(row["appeal_id"]),
                        sender_id=int(row["sender_id"]),
                        sender_role=row.get("sender_role") or "user",
                        text=row.get("text") or "",
                        created_at=_datetime(row.get("created_at")) or datetime.now(UTC),
                        content_type=row.get("content_type") or "text",
                        file_id=row.get("file_id"),
                        file_name=row.get("file_name"),
                    )
                    .on_conflict_do_nothing()
                )

            for row in _rows(USERS_DATABASE, "fsm_states"):
                raw_data = row.get("data") or "{}"
                await connection.execute(
                    insert(fsm_states)
                    .values(
                        bot_id=int(row["bot_id"]),
                        chat_id=int(row["chat_id"]),
                        user_id=int(row["user_id"]),
                        thread_id=int(row.get("thread_id") or 0),
                        business_connection_id=row.get("business_connection_id") or "",
                        destiny=row.get("destiny") or "default",
                        state=row.get("state"),
                        data=json.loads(raw_data) if isinstance(raw_data, str) else raw_data,
                    )
                    .on_conflict_do_nothing()
                )

            await connection.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM appeals), 1), EXISTS(SELECT 1 FROM appeals))"
                ),
                {"table_name": "appeals"},
            )
            await connection.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM appeal_messages), 1), EXISTS(SELECT 1 FROM appeal_messages))"
                ),
                {"table_name": "appeal_messages"},
            )
            await connection.execute(insert(data_imports).values(name=IMPORT_NAME))
        print("SQLite import completed")
        return True
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(import_sqlite())
