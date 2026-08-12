from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Appeal:
    id: int
    user_id: int
    text: str
    status: int
    answer: str | None
    created_at: str
