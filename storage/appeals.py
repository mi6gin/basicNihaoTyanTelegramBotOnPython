from datetime import UTC, datetime

from sqlalchemy import case, func, select, update

from bot.constants import CATEGORIES
from storage import get_database_engine
from storage.models import Appeal, AppealMessage
from storage.tables import appeal_messages, appeals

APPEAL_COLUMNS = (
    appeals.c.id,
    appeals.c.user_id,
    appeals.c.text,
    appeals.c.status,
    appeals.c.answer,
    appeals.c.created_at,
    appeals.c.answered_at,
    appeals.c.workflow_status,
    appeals.c.updated_at,
    appeals.c.closed_at,
    appeals.c.category,
    appeals.c.rating,
)


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _appeal(row) -> Appeal | None:
    if row is None:
        return None
    values = tuple(row)
    return Appeal(
        id=values[0],
        user_id=values[1],
        text=values[2],
        status=int(values[3]),
        answer=values[4],
        created_at=_timestamp(values[5]) or "",
        answered_at=_timestamp(values[6]),
        workflow_status=values[7],
        updated_at=_timestamp(values[8]),
        closed_at=_timestamp(values[9]),
        category=values[10],
        rating=values[11],
    )


async def create_appeal(
    user_id: int,
    appeal_text: str,
    content_type: str = "text",
    file_id: str | None = None,
    file_name: str | None = None,
    category: str = "other",
) -> int:
    now = datetime.now(UTC)
    async with get_database_engine().begin() as connection:
        appeal_id = int(
            await connection.scalar(
                appeals.insert()
                .values(user_id=user_id, text=appeal_text, created_at=now, updated_at=now, category=category)
                .returning(appeals.c.id)
            )
        )
        await connection.execute(
            appeal_messages.insert().values(
                appeal_id=appeal_id,
                sender_id=user_id,
                sender_role="user",
                text=appeal_text,
                created_at=now,
                content_type=content_type,
                file_id=file_id,
                file_name=file_name,
            )
        )
    return appeal_id


async def get_appeal_at(user_id: int, offset: int) -> tuple[Appeal | None, int]:
    async with get_database_engine().connect() as connection:
        count = int(
            await connection.scalar(select(func.count()).select_from(appeals).where(appeals.c.user_id == user_id)) or 0
        )
        row = (
            await connection.execute(
                select(*APPEAL_COLUMNS)
                .where(appeals.c.user_id == user_id)
                .order_by(appeals.c.id.desc())
                .limit(1)
                .offset(max(offset, 0))
            )
        ).one_or_none()
    return _appeal(row), count


async def get_appeal(user_id: int, appeal_id: int) -> Appeal | None:
    async with get_database_engine().connect() as connection:
        row = (
            await connection.execute(
                select(*APPEAL_COLUMNS).where((appeals.c.user_id == user_id) & (appeals.c.id == appeal_id))
            )
        ).one_or_none()
    return _appeal(row)


async def get_appeal_offset(user_id: int, appeal_id: int) -> int | None:
    condition = (appeals.c.user_id == user_id) & (appeals.c.id == appeal_id)
    async with get_database_engine().connect() as connection:
        exists = await connection.scalar(select(appeals.c.id).where(condition))
        if exists is None:
            return None
        return int(
            await connection.scalar(
                select(func.count()).select_from(appeals).where((appeals.c.user_id == user_id) & (appeals.c.id > appeal_id))
            )
            or 0
        )


def _admin_query(filter_name: str):
    statement = select(*APPEAL_COLUMNS)
    count_statement = select(func.count()).select_from(appeals)
    if filter_name in {"pending", "new"}:
        condition = appeals.c.workflow_status.in_(("new", "in_progress"))
        order = (appeals.c.updated_at.desc(), appeals.c.id.desc())
    elif filter_name in CATEGORIES:
        condition = (appeals.c.category == filter_name) & (appeals.c.workflow_status != "closed")
        order = (appeals.c.updated_at.desc(), appeals.c.id.desc())
    elif filter_name.endswith("_all") and filter_name[:-4] in CATEGORIES:
        condition = appeals.c.category == filter_name[:-4]
        order = (appeals.c.id.desc(),)
    else:
        condition = None
        order = (appeals.c.id.desc(),)
    if condition is not None:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    return statement.order_by(*order), count_statement


async def get_admin_appeal_at(offset: int, filter_name: str = "all") -> tuple[Appeal | None, int]:
    statement, count_statement = _admin_query(filter_name)
    async with get_database_engine().connect() as connection:
        count = int(await connection.scalar(count_statement) or 0)
        row = (await connection.execute(statement.limit(1).offset(max(offset, 0)))).one_or_none()
    return _appeal(row), count


async def get_admin_appeal(appeal_id: int) -> Appeal | None:
    async with get_database_engine().connect() as connection:
        row = (await connection.execute(select(*APPEAL_COLUMNS).where(appeals.c.id == appeal_id))).one_or_none()
    return _appeal(row)


async def answer_appeal(appeal_id: int, answer: str, admin_id: int = 0) -> Appeal | None:
    now = datetime.now(UTC)
    statement = (
        update(appeals)
        .where((appeals.c.id == appeal_id) & (appeals.c.workflow_status != "closed"))
        .values(status=True, answer=answer, answered_at=now, workflow_status="waiting_user", updated_at=now)
        .returning(*APPEAL_COLUMNS)
    )
    async with get_database_engine().begin() as connection:
        row = (await connection.execute(statement)).one_or_none()
        if row is None:
            return None
        await connection.execute(
            appeal_messages.insert().values(
                appeal_id=appeal_id,
                sender_id=admin_id,
                sender_role="admin",
                text=answer,
                created_at=now,
            )
        )
    return _appeal(row)


async def count_pending_appeals() -> int:
    async with get_database_engine().connect() as connection:
        return int(
            await connection.scalar(
                select(func.count()).select_from(appeals).where(appeals.c.workflow_status.in_(("new", "in_progress")))
            )
            or 0
        )


async def count_open_appeals_by_category() -> dict[str, int]:
    async with get_database_engine().connect() as connection:
        rows = (
            await connection.execute(
                select(appeals.c.category, func.count())
                .where(appeals.c.workflow_status != "closed")
                .group_by(appeals.c.category)
            )
        ).all()
    counts = dict.fromkeys(CATEGORIES, 0)
    counts.update((category, int(count)) for category, count in rows if category in counts)
    return counts


async def get_appeal_messages(appeal_id: int, limit: int = 8) -> list[AppealMessage]:
    columns = (
        appeal_messages.c.id,
        appeal_messages.c.appeal_id,
        appeal_messages.c.sender_id,
        appeal_messages.c.sender_role,
        appeal_messages.c.text,
        appeal_messages.c.created_at,
        appeal_messages.c.content_type,
        appeal_messages.c.file_id,
        appeal_messages.c.file_name,
    )
    async with get_database_engine().connect() as connection:
        rows = (
            await connection.execute(
                select(*columns)
                .where(appeal_messages.c.appeal_id == appeal_id)
                .order_by(appeal_messages.c.id.desc())
                .limit(max(limit, 1))
            )
        ).all()
    return [AppealMessage(*row[:5], _timestamp(row[5]) or "", *row[6:]) for row in reversed(rows)]


async def add_user_message(
    user_id: int,
    appeal_id: int,
    text: str,
    content_type: str = "text",
    file_id: str | None = None,
    file_name: str | None = None,
) -> Appeal | None:
    now = datetime.now(UTC)
    statement = (
        update(appeals)
        .where(
            (appeals.c.id == appeal_id)
            & (appeals.c.user_id == user_id)
            & (appeals.c.workflow_status != "closed")
        )
        .values(
            workflow_status=case((appeals.c.workflow_status == "new", "new"), else_="in_progress"),
            updated_at=now,
        )
        .returning(*APPEAL_COLUMNS)
    )
    async with get_database_engine().begin() as connection:
        row = (await connection.execute(statement)).one_or_none()
        if row is None:
            return None
        await connection.execute(
            appeal_messages.insert().values(
                appeal_id=appeal_id,
                sender_id=user_id,
                sender_role="user",
                text=text,
                created_at=now,
                content_type=content_type,
                file_id=file_id,
                file_name=file_name,
            )
        )
    return _appeal(row)


async def close_appeal(appeal_id: int) -> Appeal | None:
    now = datetime.now(UTC)
    statement = (
        update(appeals)
        .where((appeals.c.id == appeal_id) & (appeals.c.workflow_status != "closed"))
        .values(status=True, workflow_status="closed", updated_at=now, closed_at=now)
        .returning(*APPEAL_COLUMNS)
    )
    async with get_database_engine().begin() as connection:
        row = (await connection.execute(statement)).one_or_none()
    return _appeal(row)


async def rate_closed_appeal(user_id: int, appeal_id: int, rating: int) -> Appeal | None:
    if rating not in {-1, 1}:
        return None
    statement = (
        update(appeals)
        .where(
            (appeals.c.id == appeal_id)
            & (appeals.c.user_id == user_id)
            & (appeals.c.workflow_status == "closed")
            & appeals.c.rating.is_(None)
        )
        .values(rating=rating, rated_at=datetime.now(UTC))
        .returning(*APPEAL_COLUMNS)
    )
    async with get_database_engine().begin() as connection:
        row = (await connection.execute(statement)).one_or_none()
    return _appeal(row)
