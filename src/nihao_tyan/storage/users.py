from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from nihao_tyan.storage.database import get_database_engine
from nihao_tyan.storage.tables import users


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


async def get_broadcast_snapshot() -> tuple[int, int]:
    async with get_database_engine().connect() as connection:
        row = (
            await connection.execute(select(func.count(), func.coalesce(func.max(users.c.telegram_id), 0)).select_from(users))
        ).one()
    return int(row[0]), int(row[1])


async def get_broadcast_recipients(after_id: int, through_id: int, limit: int = 200) -> list[int]:
    async with get_database_engine().connect() as connection:
        rows = (
            await connection.execute(
                select(users.c.telegram_id)
                .where((users.c.telegram_id > after_id) & (users.c.telegram_id <= through_id))
                .order_by(users.c.telegram_id)
                .limit(limit)
            )
        ).scalars().all()
    return [int(user_id) for user_id in rows]


async def get_broadcast_users_page(offset: int, limit: int = 8, username_query: str = "") -> tuple[list[tuple[int, str | None, str, str | None]], int]:
    escaped = username_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    condition = users.c.username.ilike(f"%{escaped}%", escape="\\") if username_query else None
    count_query = select(func.count()).select_from(users)
    page_query = select(users.c.telegram_id, users.c.username, users.c.first_name, users.c.last_name)
    if condition is not None:
        count_query = count_query.where(condition)
        page_query = page_query.where(condition)
    async with get_database_engine().connect() as connection:
        count = int(await connection.scalar(count_query) or 0)
        rows = (
            await connection.execute(
                page_query.order_by(users.c.last_seen_at.desc(), users.c.telegram_id.desc())
                .limit(limit)
                .offset(max(offset, 0))
            )
        ).all()
    return [(int(row[0]), row[1], row[2], row[3]) for row in rows], count


async def broadcast_user_exists(telegram_id: int) -> bool:
    async with get_database_engine().connect() as connection:
        return await connection.scalar(select(users.c.telegram_id).where(users.c.telegram_id == telegram_id)) is not None
