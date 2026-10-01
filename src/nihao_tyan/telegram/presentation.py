import json
from typing import Any

from nihao_tyan.telegram.constants import LEGACY_CATEGORIES
from nihao_tyan.i18n import translate
from nihao_tyan.storage.models import Appeal, AppealMessage


def appeal_status(appeal: Appeal, language: str) -> str:
    return translate("status.closed" if appeal.workflow_status == "closed" else "status.open", language)


def appeal_category(category: str, language: str) -> str:
    safe_category = category if category in LEGACY_CATEGORIES else "other"
    return translate(f"category.{safe_category}", language)


def format_dialog(messages: list[AppealMessage], language: str, max_length: int = 2800) -> str:
    parts = []
    for message in messages:
        role = translate(f"dialog.{message.sender_role}", language)
        attachment = ""
        if message.content_type != "text":
            label = message.file_name or translate(f"attachment.{message.content_type}", language)
            attachment = f"📎 {label}\n"
        parts.append(f"{role}:\n{attachment}{message.text}")
    dialog = "\n\n".join(parts)
    if len(dialog) > max_length:
        dialog = "…" + dialog[-(max_length - 1) :]
    return dialog


def format_journal_entry(item: dict[str, Any], language: str, position: int, count: int) -> str:
    event = item.get("event", "unknown")
    known_events = {
        "incoming_message", "appeal_created", "appeal_followup", "appeal_answered", "appeal_closed",
        "appeal_rated", "bot_chat_status_changed", "broadcast_started", "broadcast_finished", "error",
    }
    event_label = translate(f"log.event.{event}", language) if event in known_events else str(event)
    lines = [translate("admin.record_header", language, position=position, count=count, time=item.get("time", "—"), event=event_label)]
    if item.get("chat_id") is not None:
        lines.append(
            translate(
                "admin.record_chat",
                language,
                title=item.get("chat_title") or "—",
                chat_type=item.get("chat_type") or "—",
                chat_id=item["chat_id"],
            )
        )
    if item.get("user_id") is not None:
        name = " ".join(filter(None, [item.get("first_name"), item.get("last_name")])) or "—"
        username = f"@{item['username']}" if item.get("username") else "—"
        lines.append(translate("admin.record_user", language, name=name, username=username, user_id=item["user_id"]))
    if item.get("appeal_id") is not None:
        lines.append(translate("admin.record_appeal", language, appeal_id=item["appeal_id"]))
    if item.get("rating") in {-1, 1}:
        label = translate("support.rating_yes" if item["rating"] == 1 else "support.rating_no", language)
        lines.append(translate("admin.rating", language, rating=label))
    if item.get("category") in LEGACY_CATEGORIES:
        lines.append(translate("admin.record_category", language, category=appeal_category(item["category"], language)))
    if item.get("new_status"):
        lines.append(translate("admin.record_status", language, old=item.get("old_status") or "—", new=item["new_status"]))
    if item.get("content_type"):
        lines.append(translate("admin.record_content_type", language, content_type=item["content_type"]))
    if item.get("text"):
        lines.append(translate("admin.record_text", language, text=item["text"]))
    if item.get("caption"):
        lines.append(translate("admin.record_caption", language, caption=item["caption"]))
    if item.get("attachment"):
        lines.append(translate("admin.record_attachment", language, attachment=json.dumps(item["attachment"], ensure_ascii=False)))
    if item.get("details"):
        lines.append(translate("admin.record_details", language, details=item["details"]))
    if event in {"broadcast_started", "broadcast_finished"}:
        kind = item.get("kind")
        if kind in {"news", "ad"}:
            lines.append(translate("admin.record_broadcast_kind", language, kind=translate(f"broadcast.{kind}", language)))
        audience = item.get("audience")
        if audience in {"all", "admins", "selected"}:
            lines.append(translate("admin.record_broadcast_audience", language, audience=translate(f"broadcast.audience_{audience}", language)))
        if item.get("admin_id") is not None:
            lines.append(translate("admin.record_broadcast_admin", language, admin_id=item["admin_id"]))
        if event == "broadcast_started":
            lines.append(translate("admin.record_broadcast_recipients", language, count=item.get("recipients", 0)))
        else:
            lines.append(
                translate(
                    "broadcast.finished", language,
                    sent=item.get("sent", 0), unavailable=item.get("unavailable", 0), failed=item.get("failed", 0),
                )
            )
    result = "\n\n".join(lines)
    return result if len(result) <= 3800 else result[:3799] + "…"
