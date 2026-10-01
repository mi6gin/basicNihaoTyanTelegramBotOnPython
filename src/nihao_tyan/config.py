import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _read_admin_ids(value: str) -> frozenset[int]:
    if not value.strip():
        return frozenset()

    try:
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise RuntimeError("ADMIN_IDS должен содержать Telegram ID через запятую") from error


def _read_bool(value: str, variable_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{variable_name} должен содержать true или false")


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: frozenset[int]
    log_level: str
    drop_pending_updates: bool


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL не задан. Скопируйте .env.example в .env")

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=_read_admin_ids(os.getenv("ADMIN_IDS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        drop_pending_updates=_read_bool(os.getenv("DROP_PENDING_UPDATES", "false"), "DROP_PENDING_UPDATES"),
    )


settings = load_settings()
