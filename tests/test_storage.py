import os
import unittest

from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Chat
from sqlalchemy.ext.asyncio import create_async_engine

import storage.appeals as appeals
import storage.chats as chats
import storage.users as users
from storage import set_database_engine
from storage.fsm import PostgreSQLStorage
from storage.tables import metadata

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine(TEST_DATABASE_URL)
        set_database_engine(self.engine)
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def add_user(self, user_id: int, language: str = "ru") -> None:
        await users.save_user(user_id, f"user{user_id}", "Test", None, language)

    async def test_user_language_is_preserved_and_can_be_changed(self) -> None:
        self.assertEqual(await users.save_user(7, "name", "Test", None, "en"), "en")
        await users.set_user_language(7, "ru")
        self.assertEqual(await users.save_user(7, None, "Changed", "User", "en"), "ru")
        self.assertEqual(await users.get_user_language(7), "ru")

    async def test_known_users_and_group_status_are_preserved(self) -> None:
        await self.add_user(7)
        await users.save_user(7, "updated", "Changed", "Name", "en")
        user, count = await users.get_user_at(0)
        self.assertEqual(count, 1)
        self.assertEqual(user[1:5], ("updated", "Changed", "Name", "ru"))
        chat = Chat(id=-1001, type="supergroup", title="Support group", username="support_group")
        await chats.save_chat(chat, "administrator")
        await chats.save_chat(chat)
        group, count = await chats.get_chat_at(0)
        self.assertEqual(count, 1)
        self.assertEqual(group[0:5], (-1001, "supergroup", "Support group", "support_group", "administrator"))
        self.assertEqual(await chats.count_active_chats(), 1)
        await chats.save_chat(chat, "left")
        self.assertEqual(await chats.count_active_chats(), 0)
        self.assertEqual((await chats.get_chat_at(0))[0][4], "left")

    async def test_appeal_supports_dialog_until_closed(self) -> None:
        await self.add_user(7)
        appeal_id = await appeals.create_appeal(7, "First problem", category="technical")
        answered = await appeals.answer_appeal(appeal_id, "First answer", admin_id=42)
        self.assertEqual((answered.answer, answered.workflow_status), ("First answer", "waiting_user"))
        self.assertEqual(await appeals.count_pending_appeals(), 0)
        followup = await appeals.add_user_message(7, appeal_id, "More details")
        self.assertEqual(followup.workflow_status, "in_progress")
        pending, count = await appeals.get_admin_appeal_at(0, "pending")
        self.assertEqual((pending.id, count), (appeal_id, 1))
        await appeals.answer_appeal(appeal_id, "Second answer", admin_id=42)
        messages = await appeals.get_appeal_messages(appeal_id)
        self.assertEqual([message.sender_role for message in messages], ["user", "admin", "user", "admin"])
        self.assertIsNotNone(await appeals.close_appeal(appeal_id))
        self.assertIsNone(await appeals.answer_appeal(appeal_id, "Too late", admin_id=42))

    async def test_admin_filters_categories_and_attachments(self) -> None:
        await self.add_user(7)
        await self.add_user(8)
        technical = await appeals.create_appeal(7, "Broken", "photo", "photo-id", category="technical")
        await appeals.create_appeal(8, "Idea", category="suggestion")
        item, count = await appeals.get_admin_appeal_at(0, "technical")
        self.assertEqual((item.id, count), (technical, 1))
        counts = await appeals.count_open_appeals_by_category()
        self.assertEqual((counts["technical"], counts["suggestion"]), (1, 1))
        await appeals.add_user_message(7, technical, "Log", "document", "doc-id", "error.log")
        messages = await appeals.get_appeal_messages(technical)
        self.assertEqual([message.content_type for message in messages], ["photo", "document"])
        self.assertEqual(messages[1].file_name, "error.log")

    async def test_fsm_state_and_data_survive_new_storage_instance(self) -> None:
        key = StorageKey(bot_id=1, chat_id=2, user_id=3)
        storage = PostgreSQLStorage(self.engine)
        await storage.set_state(key, "SupportState:waiting_for_text")
        await storage.set_data(key, {"prompt_message_id": 10})
        reopened = PostgreSQLStorage(self.engine)
        self.assertEqual(await reopened.get_state(key), "SupportState:waiting_for_text")
        self.assertEqual(await reopened.get_data(key), {"prompt_message_id": 10})
