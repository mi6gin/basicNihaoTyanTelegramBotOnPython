"""Private daily activity journals for incoming Telegram messages and bot actions."""

import asyncio
import json
import logging
import os
import re
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Bot
from aiogram.types import BufferedInputFile, Message, Update
from sqlalchemy.exc import SQLAlchemyError

from nihao_tyan.telegram.constants import CATEGORIES
from nihao_tyan.i18n import telegram_language
from nihao_tyan.config import settings
from nihao_tyan.storage.database import DATA_DIRECTORY
from nihao_tyan.storage.chats import save_chat
from nihao_tyan.storage.users import save_user

TIMEZONE = ZoneInfo("Asia/Almaty")
FILE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.jsonl$")
MAX_DAILY_FILES = 30
JOURNAL_DIRECTORY = DATA_DIRECTORY / "logs"
_active_journal: "DailyJournal | None" = None
logger = logging.getLogger(__name__)
MAX_ERROR_FILE_BYTES = 45 * 1024 * 1024


class DailyJournal:
    def __init__(self, directory: Path, now: Callable[[], datetime] | None = None) -> None:
        self.directory = directory
        self.now = now or (lambda: datetime.now(TIMEZONE))

    def _daily_files(self) -> list[Path]:
        if not self.directory.exists():
            return []
        paths = []
        for path in self.directory.iterdir():
            if path.is_symlink() or not path.is_file() or not FILE_NAME.fullmatch(path.name):
                continue
            try:
                datetime.strptime(path.stem, "%Y-%m-%d")
            except ValueError:
                continue
            paths.append(path)
        return sorted(paths)

    def prune(self) -> None:
        for path in self._daily_files()[:-MAX_DAILY_FILES]:
            path.unlink()

    def dates(self) -> list[str]:
        return [path.stem for path in reversed(self._daily_files())]

    def write(self, event: str, **fields: Any) -> None:
        timestamp = self.now().astimezone(TIMEZONE)
        day = timestamp.date().isoformat()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        record = {"time": timestamp.isoformat(timespec="seconds"), "event": event, **fields}
        raw = json.dumps(record, ensure_ascii=False, default=str).replace(settings.bot_token, "[REDACTED_BOT_TOKEN]")
        file_path = self.directory / f"{day}.jsonl"
        descriptor = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(raw + "\n")
        self.prune()

    def summary(self, day: str) -> dict[str, Any]:
        counters: Counter[str] = Counter()
        categories: Counter[str] = Counter()
        users: set[int] = set()
        chats: set[int] = set()
        for item in self._records(day):
            event = item.get("event")
            if isinstance(event, str):
                counters[event] += 1
            if event == "appeal_created" and item.get("category") in CATEGORIES:
                categories[item["category"]] += 1
            if event == "incoming_message" and isinstance(item.get("user_id"), int):
                users.add(item["user_id"])
            if event == "incoming_message" and item.get("chat_type") != "private" and isinstance(item.get("chat_id"), int):
                chats.add(item["chat_id"])
        return {"counts": counters, "categories": categories, "users": len(users), "chats": len(chats)}

    def file_path(self, day: str) -> Path | None:
        if not self._is_valid_day(day):
            raise ValueError("Invalid journal date")
        path = self.directory / f"{day}.jsonl"
        return path if path.is_file() and not path.is_symlink() else None

    def _records(self, day: str):
        path = self.file_path(day)
        if path is None:
            return
        with path.open(encoding="utf-8") as file:
            for line in file:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    yield item

    def entry(self, day: str, offset: int) -> tuple[dict[str, Any] | None, int]:
        count = sum(1 for _ in self._records(day))
        if offset < 0 or offset >= count:
            return None, count
        target = count - offset - 1
        for index, item in enumerate(self._records(day)):
            if index == target:
                return item, count
        return None, count

    @staticmethod
    def _is_valid_day(day: str) -> bool:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return False
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            return False
        return True


def configure_journal() -> DailyJournal:
    global _active_journal
    journal = DailyJournal(JOURNAL_DIRECTORY)
    journal.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    journal.prune()
    _active_journal = journal
    return journal


def get_journal() -> DailyJournal | None:
    return _active_journal


def record_event(event: str, **fields: Any) -> None:
    if _active_journal is None:
        return
    try:
        _active_journal.write(event, **fields)
    except OSError as error:
        sys.stderr.write(f"Could not write activity journal: {error}\n")


MESSAGE_UPDATE_TYPES = (
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "business_message",
    "edited_business_message",
)


def record_message(message: Message, update_type: str = "message", update_id: int | None = None) -> None:
    sender = message.from_user
    attachment = None
    for attribute in ("document", "audio", "video", "animation", "voice", "video_note", "sticker"):
        media = getattr(message, attribute, None)
        if media is not None:
            attachment = {
                "type": attribute,
                "file_name": getattr(media, "file_name", None),
                "mime_type": getattr(media, "mime_type", None),
                "file_size": getattr(media, "file_size", None),
            }
            break
    if attachment is None and message.photo:
        attachment = {"type": "photo", "file_size": message.photo[-1].file_size}
    content: dict[str, Any] = {}
    if message.contact:
        content["contact"] = {"phone_number": message.contact.phone_number, "first_name": message.contact.first_name}
    if message.location:
        content["location"] = {"latitude": message.location.latitude, "longitude": message.location.longitude}
    if message.poll:
        content["poll"] = {"question": message.poll.question, "options": [option.text for option in message.poll.options]}
    if message.dice:
        content["dice"] = {"emoji": message.dice.emoji, "value": message.dice.value}
    record_event(
        "incoming_message",
        update_id=update_id,
        update_type=update_type,
        message_id=message.message_id,
        chat_id=message.chat.id,
        chat_type=message.chat.type,
        chat_title=message.chat.title or getattr(message.chat, "full_name", None),
        chat_username=message.chat.username,
        user_id=sender.id if sender else None,
        username=sender.username if sender else None,
        first_name=sender.first_name if sender else None,
        last_name=sender.last_name if sender else None,
        language_code=sender.language_code if sender else None,
        sender_role="channel" if sender is None else "admin" if sender.id in settings.admin_ids else "user",
        sent_at=message.date.isoformat(),
        edited_at=message.edit_date.isoformat() if message.edit_date else None,
        content_type=message.content_type.value,
        text=message.text,
        caption=message.caption,
        attachment=attachment,
        **content,
    )


class IncomingUpdateMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: Update, data: dict[str, Any]) -> Any:
        for update_type in MESSAGE_UPDATE_TYPES:
            message = getattr(event, update_type, None)
            if message is not None:
                record_message(message, update_type, event.update_id)
                if message.from_user is not None:
                    try:
                        sender = message.from_user
                        await save_user(
                            sender.id,
                            sender.username,
                            sender.first_name,
                            sender.last_name,
                            telegram_language(sender.language_code),
                        )
                    except SQLAlchemyError:
                        logger.exception("Could not save user %s", message.from_user.id)
                if message.chat.type != "private":
                    try:
                        await save_chat(message.chat)
                    except SQLAlchemyError:
                        logger.exception("Could not save chat %s", message.chat.id)
        membership = event.my_chat_member
        if membership is not None:
            chat = membership.chat
            old_status_value = membership.old_chat_member.status
            new_status_value = membership.new_chat_member.status
            old_status = getattr(old_status_value, "value", old_status_value)
            new_status = getattr(new_status_value, "value", new_status_value)
            record_event(
                "bot_chat_status_changed",
                chat_id=chat.id,
                chat_type=chat.type,
                chat_title=chat.title or getattr(chat, "full_name", None),
                chat_username=chat.username,
                old_status=old_status,
                new_status=new_status,
                actor_id=membership.from_user.id,
                actor_username=membership.from_user.username,
            )
            if chat.type != "private":
                try:
                    await save_chat(chat, new_status)
                except SQLAlchemyError:
                    logger.exception("Could not save chat %s", chat.id)
        return await handler(event, data)


class JournalErrorHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            record_event("error", logger=record.name, level=record.levelname, details=self.format(record))
        except Exception:
            self.handleError(record)


class AdminErrorHandler(logging.Handler):
    """Send each error log record to administrators as a text document."""

    def __init__(self, bot: Bot, admin_ids: frozenset[int]) -> None:
        super().__init__(level=logging.ERROR)
        self.bot = bot
        self.admin_ids = tuple(sorted(admin_ids))
        self.loop = asyncio.get_running_loop()
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.worker = self.loop.create_task(self._send_reports())

    def emit(self, record: logging.LogRecord) -> None:
        if not self.admin_ids:
            return
        try:
            timestamp = datetime.fromtimestamp(record.created, timezone.utc).astimezone(TIMEZONE)
            filename = f"error-{timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.txt"
            report = (
                f"Time: {timestamp.isoformat(timespec='seconds')}\n"
                f"Level: {record.levelname}\n"
                f"Logger: {record.name}\n\n"
                f"{self.format(record)}\n"
            ).replace(settings.bot_token, "[REDACTED_BOT_TOKEN]")
            self.loop.call_soon_threadsafe(self.queue.put_nowait, (filename, report))
        except Exception:
            self.handleError(record)

    async def _send_reports(self) -> None:
        while True:
            filename, report = await self.queue.get()
            try:
                content = report.encode("utf-8", errors="replace")
                if len(content) > MAX_ERROR_FILE_BYTES:
                    content = content[: MAX_ERROR_FILE_BYTES - 100].decode("utf-8", errors="ignore").encode("utf-8")
                    content += b"\n\n[Report truncated to fit Telegram's document limit.]\n"
                for admin_id in self.admin_ids:
                    try:
                        await self.bot.send_document(
                            admin_id,
                            BufferedInputFile(content, filename=filename),
                            caption="Ошибка бота. Подробности в файле.",
                        )
                    except Exception as error:
                        # Logging here would create another error notification.
                        record_event("error", logger=__name__, details=f"Could not send error report to admin {admin_id}: {error}")
                        sys.stderr.write(f"Could not send error report to admin {admin_id}: {error}\n")
            finally:
                self.queue.task_done()

    async def shutdown(self) -> None:
        await asyncio.sleep(0)
        try:
            await asyncio.wait_for(self.queue.join(), timeout=20)
        except TimeoutError:
            sys.stderr.write("Timed out while sending pending error reports\n")
        finally:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
