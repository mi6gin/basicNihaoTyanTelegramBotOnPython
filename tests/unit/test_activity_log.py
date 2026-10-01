import json
import stat
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiogram import Bot, Dispatcher
from aiogram.types import Chat, Contact, Message, PhotoSize, Update, User

import nihao_tyan.services.activity_log as activity_log
from nihao_tyan.services.activity_log import TIMEZONE, DailyJournal, IncomingUpdateMiddleware, record_message
from nihao_tyan.telegram.presentation import format_journal_entry
from nihao_tyan.config import settings


class DailyJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name) / "logs"
        self.current_time = datetime(2026, 9, 22, 9, 0, tzinfo=TIMEZONE)
        self.journal = DailyJournal(self.directory, now=lambda: self.current_time)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_daily_files_and_summary(self) -> None:
        self.journal.write("incoming_message", text="Привет", user_id=7)
        self.journal.write("appeal_created", appeal_id=1, category="technical")
        self.current_time += timedelta(days=1)
        self.journal.write("appeal_answered", appeal_id=1)
        self.assertEqual(self.journal.dates(), ["2026-09-23", "2026-09-22"])
        self.assertEqual(self.journal.summary("2026-09-22")["counts"]["incoming_message"], 1)
        self.assertEqual(self.journal.summary("2026-09-22")["categories"]["technical"], 1)
        self.assertEqual(self.journal.summary("2026-09-23")["counts"]["appeal_answered"], 1)
        self.assertEqual(self.journal.summary("2026-09-24")["counts"]["incoming_message"], 0)
        self.assertEqual(stat.S_IMODE((self.directory / "2026-09-22.jsonl").stat().st_mode), 0o600)

    def test_keeps_only_30_daily_files_and_ignores_other_files(self) -> None:
        self.directory.mkdir()
        unrelated = self.directory / "notes.txt"
        unrelated.write_text("keep", encoding="utf-8")
        for day in range(31):
            self.current_time = datetime(2026, 1, 1, tzinfo=TIMEZONE) + timedelta(days=day)
            self.journal.write("incoming_message", text=str(day))
        self.assertEqual(len(self.journal.dates()), 30)
        self.assertFalse((self.directory / "2026-01-01.jsonl").exists())
        self.assertTrue((self.directory / "2026-01-31.jsonl").exists())
        self.assertTrue(unrelated.exists())

    def test_token_is_redacted_and_date_is_validated(self) -> None:
        self.journal.write("incoming_message", text=f"token={settings.bot_token}")
        raw = (self.directory / "2026-09-22.jsonl").read_text(encoding="utf-8")
        self.assertNotIn(settings.bot_token, raw)
        self.assertIn("[REDACTED_BOT_TOKEN]", raw)
        with self.assertRaises(ValueError):
            self.journal.summary("../../2026-09-22")

    def test_entry_view_reads_newest_and_validates_file(self) -> None:
        self.journal.write("incoming_message", text="first")
        self.journal.write("incoming_message", text="second")
        newest, count = self.journal.entry("2026-09-22", 0)
        self.assertEqual((newest["text"], count), ("second", 2))
        self.assertEqual(self.journal.entry("2026-09-22", 1)[0]["text"], "first")
        self.assertIsNone(self.journal.entry("2026-09-22", 2)[0])
        self.assertIsNotNone(self.journal.file_path("2026-09-22"))
        with self.assertRaises(ValueError):
            self.journal.entry("../secrets", 0)

    def test_record_message_captures_text_and_contact(self) -> None:
        user = User(id=7, is_bot=False, first_name="Test")
        chat = Chat(id=7, type="private")
        message = Message(message_id=1, date=self.current_time, chat=chat, from_user=user, text="Hello")
        contact = Message(
            message_id=2,
            date=self.current_time,
            chat=chat,
            from_user=user,
            contact=Contact(phone_number="123", first_name="A"),
        )
        photo = Message(
            message_id=3,
            date=self.current_time,
            chat=chat,
            from_user=user,
            photo=[PhotoSize(file_id="private-file-id", file_unique_id="unique", width=100, height=100, file_size=500)],
            caption="Screenshot",
        )
        with patch.object(activity_log, "_active_journal", self.journal):
            record_message(message)
            record_message(contact)
            record_message(photo)
        lines = [json.loads(line) for line in (self.directory / "2026-09-22.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["message_id"] for item in lines], [1, 2, 3])
        self.assertEqual(lines[0]["text"], "Hello")
        self.assertEqual(lines[0]["first_name"], "Test")
        self.assertEqual(lines[0]["chat_type"], "private")
        self.assertEqual(lines[0]["content_type"], "text")
        self.assertEqual(lines[0]["sent_at"], self.current_time.isoformat())
        self.assertEqual(lines[1]["contact"]["phone_number"], "123")
        self.assertEqual(lines[2]["caption"], "Screenshot")
        self.assertEqual(lines[2]["attachment"]["type"], "photo")
        self.assertNotIn("private-file-id", (self.directory / "2026-09-22.jsonl").read_text(encoding="utf-8"))

    def test_entry_is_readable_for_admin(self) -> None:
        text = format_journal_entry(
            {"time": "2026-09-22T09:00:00+05:00", "event": "incoming_message", "user_id": 7, "first_name": "Test", "text": "Hello"},
            "ru",
            1,
            2,
        )
        self.assertIn("Test", text)
        self.assertIn("Hello", text)


class IncomingUpdateMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_passes_message_to_handler_after_logging(self) -> None:
        calls = []

        async def handler(event: object, data: dict) -> str:
            calls.append((event, data))
            return "handled"

        message = Message(
            message_id=1,
            date=datetime(2026, 9, 22, tzinfo=TIMEZONE),
            chat=Chat(id=7, type="private"),
            text="Hello",
        )
        event = Update(update_id=10, message=message)
        with patch.object(activity_log, "record_message") as log_message:
            result = await IncomingUpdateMiddleware()(handler, event, {"key": "value"})
        self.assertEqual(result, "handled")
        log_message.assert_called_once_with(message, "message", 10)
        self.assertEqual(calls, [(event, {"key": "value"})])

    async def test_unhandled_message_is_still_logged(self) -> None:
        bot = Bot(token="123456:TEST")
        dispatcher = Dispatcher()
        dispatcher.update.outer_middleware(IncomingUpdateMiddleware())
        message = Message(message_id=2, date=datetime(2026, 9, 22, tzinfo=TIMEZONE), chat=Chat(id=7, type="private"), text="Unhandled")
        try:
            with patch.object(activity_log, "record_message") as log_message:
                await dispatcher.feed_update(bot, Update(update_id=11, message=message))
            log_message.assert_called_once()
            self.assertEqual(log_message.call_args.args[1:], ("message", 11))
        finally:
            await bot.session.close()

    async def test_sender_is_added_to_user_registry(self) -> None:
        sender = User(id=7, is_bot=False, first_name="Test", username="tester", language_code="en")
        message = Message(
            message_id=3,
            date=datetime(2026, 9, 22, tzinfo=TIMEZONE),
            chat=Chat(id=7, type="private"),
            from_user=sender,
            text="Hello",
        )
        event = Update(update_id=12, message=message)

        async def handler(update: object, data: dict) -> None:
            return None

        with patch.object(activity_log, "record_message"), patch.object(activity_log, "save_user") as save_user:
            await IncomingUpdateMiddleware()(handler, event, {})
        save_user.assert_called_once_with(7, "tester", "Test", None, "en")

    async def test_group_membership_is_recorded(self) -> None:
        membership = SimpleNamespace(
            chat=Chat(id=-1001, type="supergroup", title="Team"),
            old_chat_member=SimpleNamespace(status=SimpleNamespace(value="left")),
            new_chat_member=SimpleNamespace(status=SimpleNamespace(value="member")),
            from_user=User(id=7, is_bot=False, first_name="Admin"),
        )
        update = SimpleNamespace(my_chat_member=membership)

        async def handler(event: object, data: dict) -> None:
            return None

        with patch.object(activity_log, "save_chat") as save_chat, patch.object(activity_log, "record_event") as record_event:
            await IncomingUpdateMiddleware()(handler, update, {})
        save_chat.assert_called_once_with(membership.chat, "member")
        self.assertEqual(record_event.call_args.args[0], "bot_chat_status_changed")
