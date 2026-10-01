import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

load_dotenv()

DATA_DIRECTORY = Path(os.getenv("BOT_DATA_DIR", "data")).expanduser().resolve()
USERS_DATABASE = DATA_DIRECTORY / "users.db"
APPEALS_DATABASE = DATA_DIRECTORY / "appeals.db"

_engine: AsyncEngine | None = None


def create_database_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def set_database_engine(engine: AsyncEngine) -> None:
    global _engine
    _engine = engine


def get_database_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not configured")
    return _engine
