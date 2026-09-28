from aiogram.types import Chat
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert

from storage import get_database_engine
from storage.tables import bot_chats


async def save_chat(chat: Chat, bot_status: str = "active") -> None:
    statement = insert(bot_chats).values(
        chat_id=chat.id,
        chat_type=chat.type,
        title=chat.title,
        username=chat.username,
        bot_status=bot_status,
    )
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[bot_chats.c.chat_id],
        set_={
            "chat_type": excluded.chat_type,
            "title": excluded.title,
            "username": excluded.username,
            "bot_status": case(
                (
                    (excluded.bot_status == "active") & bot_chats.c.bot_status.not_in(("left", "kicked")),
                    bot_chats.c.bot_status,
                ),
                else_=excluded.bot_status,
            ),
            "last_seen_at": func.now(),
        },
    )
    async with get_database_engine().begin() as connection:
        await connection.execute(statement)


async def get_chat_at(offset: int) -> tuple[tuple | None, int]:
    safe_offset = max(offset, 0)
    async with get_database_engine().connect() as connection:
        count = int(await connection.scalar(select(func.count()).select_from(bot_chats)) or 0)
        row = (
            await connection.execute(
                select(
                    bot_chats.c.chat_id,
                    bot_chats.c.chat_type,
                    bot_chats.c.title,
                    bot_chats.c.username,
                    bot_chats.c.bot_status,
                    bot_chats.c.first_seen_at,
                    bot_chats.c.last_seen_at,
                )
                .order_by(bot_chats.c.last_seen_at.desc(), bot_chats.c.chat_id.desc())
                .limit(1)
                .offset(safe_offset)
            )
        ).one_or_none()
    if row is None:
        return None, count
    values = tuple(row)
    return (*values[:5], values[5].isoformat(), values[6].isoformat()), count


async def count_active_chats() -> int:
    async with get_database_engine().connect() as connection:
        return int(
            await connection.scalar(
                select(func.count()).select_from(bot_chats).where(bot_chats.c.bot_status.not_in(("left", "kicked")))
            )
            or 0
        )
