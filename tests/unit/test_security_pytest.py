"""Regression checks for group menus and stale workflow buttons."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, User

from nihao_tyan.telegram import common
from nihao_tyan.telegram.callbacks import Callback
from nihao_tyan.telegram.handlers import admin, broadcast, main_menu, support
from nihao_tyan.telegram.keyboards.main_menu import main_menu_keyboard
from nihao_tyan.telegram.states import AdminState, SupportState
from nihao_tyan.storage.models import Appeal


def run(coroutine):
    return asyncio.run(coroutine)


def make_callback(action, *, owner=101, clicker=101, chat_type="supergroup", message_id=10, value=None):
    chat_id = clicker if chat_type == "private" else -100123
    chat = Chat(id=chat_id, type=chat_type, title="Group" if chat_type != "private" else None)
    message = Message(message_id=message_id, date=datetime.now(UTC), chat=chat, text="Menu")
    user = User(id=clicker, is_bot=False, first_name="User")
    return SimpleNamespace(
        data=Callback(action, owner, value).pack(),
        from_user=user,
        message=message,
        answer=AsyncMock(),
    )


@pytest.fixture(autouse=True)
def no_user_database(monkeypatch):
    monkeypatch.setattr(common, "sync_user", AsyncMock(return_value="ru"))


def test_group_start_shows_owner_buttons_without_admin_panel(monkeypatch):
    monkeypatch.setattr("nihao_tyan.telegram.keyboards.main_menu.settings", SimpleNamespace(admin_ids={101}))
    group_message = SimpleNamespace(
        from_user=User(id=101, is_bot=False, first_name="Owner"),
        chat=Chat(id=-100123, type="supergroup", title="Group"),
        answer=AsyncMock(),
    )

    run(main_menu.send_main_menu(group_message, "ru"))

    markup = group_message.answer.await_args.kwargs["reply_markup"]
    callbacks = {button.callback_data for row in markup.inline_keyboard for button in row}
    assert callbacks == {"support:101", "language:101"}
    private_callbacks = {button.callback_data for row in main_menu_keyboard(101, "ru").inline_keyboard for button in row}
    assert "admin:101" in private_callbacks


@pytest.mark.parametrize("action", ["main", "language", "setlang"])
def test_owner_can_use_allowed_group_menu_buttons(action):
    callback = make_callback(action, value="en" if action == "setlang" else None)

    authorized = run(common.authorize_callback(callback, allow_group=True))

    assert authorized is not None
    assert authorized[1].owner_id == 101
    callback.answer.assert_not_awaited()


@pytest.mark.parametrize("action", ["main", "language", "setlang", "support", "admin"])
def test_other_group_member_cannot_use_menu(action):
    callback = make_callback(action, clicker=202, value="en" if action == "setlang" else None)

    assert run(common.authorize_callback(callback, allow_group=True)) is None
    assert callback.answer.await_args.kwargs["show_alert"] is True
    assert "другому пользователю" in callback.answer.await_args.args[0]


@pytest.mark.parametrize("action", ["support", "admin", "broadcast", "report"])
def test_private_workflow_buttons_are_rejected_in_group_even_for_owner(action):
    callback = make_callback(action)

    assert run(common.authorize_callback(callback, allow_group=True)) is None
    assert "личном чате" in callback.answer.await_args.args[0]


def test_admin_handler_cannot_open_from_group(monkeypatch):
    callback = make_callback("admin")
    count_appeals = AsyncMock()
    monkeypatch.setattr(admin, "count_pending_appeals", count_appeals)

    run(admin.open_admin(callback, AsyncMock()))

    count_appeals.assert_not_awaited()
    assert "личном чате" in callback.answer.await_args.args[0]


def test_old_category_button_cannot_advance_current_support_state(monkeypatch):
    callback = make_callback("category", chat_type="private", message_id=11, value="technical")
    state = AsyncMock()
    state.get_state.return_value = SupportState.waiting_for_category.state
    state.get_data.return_value = {"prompt_message_id": 12}
    edit = AsyncMock()
    monkeypatch.setattr(support, "edit_screen", edit)

    run(support.choose_appeal_category(callback, state))

    edit.assert_not_awaited()
    state.set_state.assert_not_awaited()
    state.clear.assert_not_awaited()
    assert "неактуально" in callback.answer.await_args.args[0]


def test_old_cancel_button_cannot_clear_current_support_state():
    callback = make_callback("cancel", chat_type="private", message_id=11)
    state = AsyncMock()
    state.get_state.return_value = SupportState.waiting_for_text.state
    state.get_data.return_value = {"prompt_message_id": 12}

    run(support.cancel_appeal(callback, state, AsyncMock()))

    state.clear.assert_not_awaited()
    assert "неактуально" in callback.answer.await_args.args[0]


def test_old_broadcast_confirmation_cannot_send_or_clear_new_draft(monkeypatch):
    callback = make_callback("broadcastsend", chat_type="private", message_id=11)
    state = AsyncMock()
    state.get_state.return_value = AdminState.waiting_for_broadcast_confirmation.state
    state.get_data.return_value = {
        "confirm_message_id": 12,
        "kind": "news",
        "audience": "all",
        "text": "Hello",
    }
    send = AsyncMock()
    monkeypatch.setattr(broadcast, "settings", SimpleNamespace(admin_ids={101}))
    monkeypatch.setattr(broadcast, "deliver_broadcast", send)

    run(broadcast.confirm_broadcast(callback, state, AsyncMock()))

    send.assert_not_awaited()
    state.clear.assert_not_awaited()
    assert "недоступен" in callback.answer.await_args.args[0]


def test_old_admin_cancel_cannot_clear_new_answer_state(monkeypatch):
    callback = make_callback("admincancel", chat_type="private", message_id=11, value="5")
    state = AsyncMock()
    state.get_state.return_value = AdminState.waiting_for_answer.state
    state.get_data.return_value = {"appeal_id": 5, "prompt_message_id": 12}
    monkeypatch.setattr(admin, "settings", SimpleNamespace(admin_ids={101}))

    run(admin.cancel_admin_answer(callback, state))

    state.clear.assert_not_awaited()
    assert "неактуален" in callback.answer.await_args.args[0]


def test_group_message_cannot_create_support_request(monkeypatch):
    message = SimpleNamespace(
        from_user=User(id=101, is_bot=False, first_name="User"),
        chat=Chat(id=-100123, type="supergroup", title="Group"),
        text="Private issue",
        answer=AsyncMock(),
    )
    state = AsyncMock()
    create = AsyncMock()
    monkeypatch.setattr(support, "sync_user", AsyncMock(return_value="ru"))
    monkeypatch.setattr(support, "create_appeal", create)

    run(support.receive_appeal(message, state, AsyncMock()))

    create.assert_not_awaited()
    state.clear.assert_awaited_once()
    assert "личном чате" in message.answer.await_args.args[0]


def test_quick_reply_requires_preview_before_sending(monkeypatch):
    callback = make_callback("adminquick", chat_type="private", message_id=11, value="5.details")
    state = AsyncMock()
    state.get_state.return_value = AdminState.waiting_for_answer.state
    state.get_data.return_value = {"appeal_id": 5, "prompt_message_id": 11}
    edit = AsyncMock(return_value=11)
    save = AsyncMock()
    monkeypatch.setattr(admin, "settings", SimpleNamespace(admin_ids={101}))
    monkeypatch.setattr(admin, "edit_screen", edit)
    monkeypatch.setattr(admin, "save_admin_answer", save)

    run(admin.choose_admin_quick_reply(callback, state))

    save.assert_not_awaited()
    state.update_data.assert_awaited_once()
    assert "quick_text" in state.update_data.await_args.kwargs
    assert "Отправить" in edit.await_args.args[1]


def test_confirmed_quick_reply_uses_current_answer_state(monkeypatch):
    callback = make_callback("adminquicksend", chat_type="private", message_id=11, value="5")
    state = AsyncMock()
    state.get_state.return_value = AdminState.waiting_for_answer.state
    state.get_data.return_value = {"appeal_id": 5, "prompt_message_id": 11, "quick_text": "Готовый ответ"}
    appeal = Appeal(5, 7, "Problem", 1, None, "2026-01-01T00:00:00+00:00", None, "waiting_user", None, None, "technical")
    save = AsyncMock(return_value=(appeal, True))
    edit = AsyncMock(return_value=11)
    monkeypatch.setattr(admin, "settings", SimpleNamespace(admin_ids={101}))
    monkeypatch.setattr(admin, "save_admin_answer", save)
    monkeypatch.setattr(admin, "edit_screen", edit)

    run(admin.send_admin_quick_reply(callback, state, AsyncMock()))

    state.clear.assert_awaited_once()
    save.assert_awaited_once()
    assert save.await_args.args[1:] == (5, "Готовый ответ", 101)
    assert "сохранён" in edit.await_args.args[1]


def test_rating_button_is_bound_to_appeal_owner(monkeypatch):
    callback = make_callback("rateappeal", owner=101, clicker=202, chat_type="private", value="5.1")
    rate = AsyncMock()
    monkeypatch.setattr(support, "rate_closed_appeal", rate)

    run(support.rate_user_appeal(callback))

    rate.assert_not_awaited()
    assert "другому пользователю" in callback.answer.await_args.args[0]
