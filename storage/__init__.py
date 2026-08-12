from pathlib import Path

DATA_DIRECTORY = Path(__file__).resolve().parent.parent / "data"
USERS_DATABASE = DATA_DIRECTORY / "users.db"
APPEALS_DATABASE = DATA_DIRECTORY / "appeals.db"


def initialize_storage() -> None:
    from storage.appeals import initialize_appeals
    from storage.users import initialize_users

    DATA_DIRECTORY.mkdir(exist_ok=True)
    initialize_users()
    initialize_appeals()
