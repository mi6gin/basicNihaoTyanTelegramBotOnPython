import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from nihao_tyan.telegram.constants import MAX_ANSWER_LENGTH
from nihao_tyan.telegram.handlers import admin
from nihao_tyan.telegram.handlers.admin import parse_appeal_position, parse_list_position
from nihao_tyan.telegram.keyboards.admin import admin_categories_keyboard, admin_empty_category_keyboard, admin_menu_keyboard
from nihao_tyan.storage.models import Appeal


class AdminCallbackParsingTests(unittest.TestCase):
    def test_list_position(self) -> None:
        self.assertEqual(parse_list_position("pending.3"), ("pending", 3))
        self.assertEqual(parse_list_position("all.2"), ("all", 2))
        self.assertEqual(parse_list_position("technical.1"), ("technical", 1))
        self.assertEqual(parse_list_position("technical_all.1"), ("technical_all", 1))
        self.assertEqual(parse_list_position("invalid"), ("pending", 0))

    def test_appeal_position(self) -> None:
        self.assertEqual(parse_appeal_position("12.new.4"), (12, "new", 4))
        self.assertEqual(parse_appeal_position("12.technical_all.4"), (12, "technical_all", 4))
        self.assertEqual(parse_appeal_position("12.invalid.bad"), (12, "all", 0))
        self.assertIsNone(parse_appeal_position("invalid"))

    def test_menu_and_category_buttons(self) -> None:
        menu = admin_menu_keyboard(42, "ru")
        self.assertEqual(menu.inline_keyboard[0][0].callback_data, "adminlist:42:pending.0")
        categories = admin_categories_keyboard(42, "ru", {"technical": 3})
        self.assertIn("3", categories.inline_keyboard[0][0].text)
        self.assertEqual(categories.inline_keyboard[0][0].callback_data, "adminlist:42:technical.0")
        empty = admin_empty_category_keyboard(42, "ru", "technical")
        self.assertEqual(empty.inline_keyboard[0][0].callback_data, "adminlist:42:technical_all.0")


class AdminAnswerTests(unittest.IsolatedAsyncioTestCase):
    def make_message(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(id=42, type="private"),
            text=text,
            answer=AsyncMock(),
        )

    async def test_answer_is_saved_and_user_is_notified(self) -> None:
        message = self.make_message("Solution")
        state = AsyncMock()
        state.get_data.return_value = {"appeal_id": 5, "prompt_message_id": 9}
        bot = AsyncMock()
        appeal = Appeal(
            5,
            7,
            "Problem",
            1,
            "Solution",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:01:00+00:00",
            "waiting_user",
            "2026-01-01T00:01:00+00:00",
            None,
            "technical",
        )

        with (
            patch.object(admin, "sync_user", return_value="en"),
            patch.object(admin, "answer_appeal", return_value=appeal) as answer,
            patch.object(admin, "get_user_language", return_value="ru"),
            patch.object(admin, "settings", SimpleNamespace(admin_ids=(42,))),
        ):
            await admin.receive_admin_answer(message, state, bot)

        answer.assert_called_once_with(5, "Solution", 42)
        state.clear.assert_awaited_once()
        bot.delete_message.assert_awaited_once_with(42, 9)
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.args[0], 7)
        message.answer.assert_awaited_once()

    async def test_too_long_answer_keeps_state(self) -> None:
        message = self.make_message("x" * (MAX_ANSWER_LENGTH + 1))
        state = AsyncMock()
        bot = AsyncMock()

        with (
            patch.object(admin, "sync_user", return_value="ru"),
            patch.object(admin, "answer_appeal") as answer,
            patch.object(admin, "settings", SimpleNamespace(admin_ids=(42,))),
        ):
            await admin.receive_admin_answer(message, state, bot)

        answer.assert_not_called()
        state.clear.assert_not_awaited()
        message.answer.assert_awaited_once()

    async def test_empty_answer_keeps_state(self) -> None:
        message = self.make_message("   ")
        state = AsyncMock()
        bot = AsyncMock()

        with (
            patch.object(admin, "sync_user", return_value="ru"),
            patch.object(admin, "answer_appeal") as answer,
            patch.object(admin, "settings", SimpleNamespace(admin_ids=(42,))),
        ):
            await admin.receive_admin_answer(message, state, bot)

        answer.assert_not_called()
        state.clear.assert_not_awaited()
        message.answer.assert_awaited_once()
