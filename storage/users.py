from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from storage import get_database_engine
from storage.tables import users


async def save_user(
    telegram_id: int,
    username: str | None,
    first_name: str,
    last_name: str | None,
    initial_language: str,
) -> str:
    statement = insert(users).values(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language=initial_language,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[users.c.telegram_id],
        set_={
            "username": statement.excluded.username,
            "first_name": statement.excluded.first_name,
            "last_name": statement.excluded.last_name,
            "last_seen_at": func.now(),
        },
    ).returning(users.c.language)
    async with get_database_engine().begin() as connection:
        return str(await connection.scalar(statement))


async def set_user_language(telegram_id: int, language: str) -> None:
    async with get_database_engine().begin() as connection:
        await connection.execute(users.update().where(users.c.telegram_id == telegram_id).values(language=language))


async def get_user_language(telegram_id: int) -> str:
    async with get_database_engine().connect() as connection:
        language = await connection.scalar(select(users.c.language).where(users.c.telegram_id == telegram_id))
    return str(language or "ru")


async def get_user_at(offset: int) -> tuple[tuple | None, int]:
    safe_offset = max(offset, 0)
    async with get_database_engine().connect() as connection:
        count = int(await connection.scalar(select(func.count()).select_from(users)) or 0)
        row = (
            await connection.execute(
                select(
                    users.c.telegram_id,
                    users.c.username,
                    users.c.first_name,
                    users.c.last_name,
                    users.c.language,
                    users.c.registered_at,
                    users.c.last_seen_at,
                )
                .order_by(users.c.last_seen_at.desc(), users.c.telegram_id.desc())
                .limit(1)
                .offset(safe_offset)
            )
        ).one_or_none()
    if row is None:
        return None, count
    values = tuple(row)
    return (*values[:5], values[5].isoformat(), values[6].isoformat()), count
