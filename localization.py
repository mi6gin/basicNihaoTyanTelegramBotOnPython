import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SUPPORTED_LANGUAGES = {"ru", "en"}
LOCALES_DIRECTORY = Path(__file__).resolve().parent / "locales"


def telegram_language(language_code: str | None) -> str:
    return language_code if language_code in SUPPORTED_LANGUAGES else "ru"


@lru_cache(maxsize=2)
def _load_language(language: str) -> dict[str, str]:
    path = LOCALES_DIRECTORY / f"{language}.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def translate(code: str, language: str, **values: Any) -> str:
    selected = language if language in SUPPORTED_LANGUAGES else "ru"
    return _load_language(selected)[code].format(**values)
