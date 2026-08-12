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


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    log_level: str


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env")

    return Settings(
        bot_token=bot_token,
        admin_ids=_read_admin_ids(os.getenv("ADMIN_IDS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()
