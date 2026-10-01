from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Appeal:
    id: int
    user_id: int
    text: str
    status: int
    answer: str | None
    created_at: str
    answered_at: str | None
    workflow_status: str
    updated_at: str | None
    closed_at: str | None
    category: str
    rating: int | None = None


@dataclass(frozen=True, slots=True)
class AppealMessage:
    id: int
    appeal_id: int
    sender_id: int
    sender_role: str
    text: str
    created_at: str
    content_type: str
    file_id: str | None
    file_name: str | None
