import asyncio
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey


class SQLiteStorage(BaseStorage):
    """Постоянное FSM-хранилище aiogram в SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = asyncio.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @staticmethod
    def _key(key: StorageKey) -> tuple[int, int, int, int, str, str]:
        return (
            key.bot_id,
            key.chat_id,
            key.user_id,
            key.thread_id or 0,
            key.business_connection_id or "",
            key.destiny,
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_states (
                    bot_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    thread_id INTEGER NOT NULL DEFAULT 0,
                    business_connection_id TEXT NOT NULL DEFAULT '',
                    destiny TEXT NOT NULL DEFAULT 'default',
                    state TEXT,
                    data TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (
                        bot_id, chat_id, user_id, thread_id,
                        business_connection_id, destiny
                    )
                )
                """
            )

    def _write_state(self, key: StorageKey, state: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fsm_states (
                    bot_id, chat_id, user_id, thread_id,
                    business_connection_id, destiny, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET state = excluded.state
                """,
                (*self._key(key), state),
            )

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_value = state.state if isinstance(state, State) else state
        async with self._lock:
            await asyncio.to_thread(self._write_state, key, state_value)

    def _read_state(self, key: StorageKey) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state FROM fsm_states
                WHERE bot_id = ? AND chat_id = ? AND user_id = ?
                  AND thread_id = ? AND business_connection_id = ? AND destiny = ?
                """,
                self._key(key),
            ).fetchone()
        return row[0] if row else None

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._lock:
            return await asyncio.to_thread(self._read_state, key)

    def _write_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        serialized = json.dumps(dict(data), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fsm_states (
                    bot_id, chat_id, user_id, thread_id,
                    business_connection_id, destiny, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET data = excluded.data
                """,
                (*self._key(key), serialized),
            )

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._write_data, key, data)

    def _read_data(self, key: StorageKey) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT data FROM fsm_states
                WHERE bot_id = ? AND chat_id = ? AND user_id = ?
                  AND thread_id = ? AND business_connection_id = ? AND destiny = ?
                """,
                self._key(key),
            ).fetchone()
        return json.loads(row[0]) if row else {}

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._read_data, key)

    async def update_data(
        self,
        key: StorageKey,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            current = await asyncio.to_thread(self._read_data, key)
            current.update(data)
            await asyncio.to_thread(self._write_data, key, current)
            return current.copy()

    async def close(self) -> None:
        return None
