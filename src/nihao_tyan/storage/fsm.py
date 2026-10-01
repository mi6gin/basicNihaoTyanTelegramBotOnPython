from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from nihao_tyan.storage.tables import fsm_states


class PostgreSQLStorage(BaseStorage):
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @staticmethod
    def _key(key: StorageKey) -> dict[str, Any]:
        return {
            "bot_id": key.bot_id,
            "chat_id": key.chat_id,
            "user_id": key.user_id,
            "thread_id": key.thread_id or 0,
            "business_connection_id": key.business_connection_id or "",
            "destiny": key.destiny,
        }

    @staticmethod
    def _condition(key: StorageKey):
        values = PostgreSQLStorage._key(key)
        return (
            (fsm_states.c.bot_id == values["bot_id"])
            & (fsm_states.c.chat_id == values["chat_id"])
            & (fsm_states.c.user_id == values["user_id"])
            & (fsm_states.c.thread_id == values["thread_id"])
            & (fsm_states.c.business_connection_id == values["business_connection_id"])
            & (fsm_states.c.destiny == values["destiny"])
        )

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_value = state.state if isinstance(state, State) else state
        statement = insert(fsm_states).values(**self._key(key), state=state_value)
        statement = statement.on_conflict_do_update(
            index_elements=[
                fsm_states.c.bot_id,
                fsm_states.c.chat_id,
                fsm_states.c.user_id,
                fsm_states.c.thread_id,
                fsm_states.c.business_connection_id,
                fsm_states.c.destiny,
            ],
            set_={"state": state_value},
        )
        async with self.engine.begin() as connection:
            await connection.execute(statement)

    async def get_state(self, key: StorageKey) -> str | None:
        async with self.engine.connect() as connection:
            return await connection.scalar(select(fsm_states.c.state).where(self._condition(key)))

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        value = dict(data)
        statement = insert(fsm_states).values(**self._key(key), data=value)
        statement = statement.on_conflict_do_update(
            index_elements=[
                fsm_states.c.bot_id,
                fsm_states.c.chat_id,
                fsm_states.c.user_id,
                fsm_states.c.thread_id,
                fsm_states.c.business_connection_id,
                fsm_states.c.destiny,
            ],
            set_={"data": value},
        )
        async with self.engine.begin() as connection:
            await connection.execute(statement)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self.engine.connect() as connection:
            data = await connection.scalar(select(fsm_states.c.data).where(self._condition(key)))
        return dict(data or {})

    async def close(self) -> None:
        return None
