"""Administrator workflow for news and promotional broadcasts."""

import logging
from urllib.parse import urlsplit

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.broadcast import broadcast_lock, deliver_broadcast
from bot.callbacks import Callback
from bot.common import authorize_callback, edit_screen, sync_user
from bot.keyboards.admin import (
    broadcast_ad_keyboard,
    broadcast_audience_keyboard,
    broadcast_cancel_keyboard,
    broadcast_confirm_keyboard,
    broadcast_menu_keyboard,
    broadcast_users_keyboard,
)
from bot.states import AdminState
from localization import translate
from settings import settings
from storage.users import broadcast_user_exists, get_broadcast_snapshot, get_broadcast_users_page

logger = logging.getLogger(__name__)
router = Router(name="broadcast")
MAX_BROADCAST_TEXT_LENGTH = 4000
MAX_BUTTON_TEXT_LENGTH = 64
MAX_BUTTON_URL_LENGTH = 2048
MAX_SELECTED_USERS = 100
SELECTOR_PAGE_SIZE = 8


async def authorize_broadcast_callback(callback: CallbackQuery) -> tuple[str, Callback] | None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return None
    language, data = authorized
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer(translate("admin.denied", language), show_alert=True)
        return None
    return language, data


async def authorize_broadcast_message(message: Message) -> str | None:
    if message.from_user is None:
        return None
    language = await sync_user(message.from_user)
    if message.chat.type != "private":
        await message.answer(translate("error.private_chat_only", language))
        return None
    if message.from_user.id not in settings.admin_ids:
        await message.answer(translate("admin.denied", language))
        return None
    return language


def valid_button_url(value: str) -> bool:
    if not value or len(value) > MAX_BUTTON_URL_LENGTH or any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.username is None and parsed.password is None
    except ValueError:
        return False


def selected_user_ids(draft: dict) -> tuple[int, ...]:
    values = draft.get("selected_ids", [])
    if not isinstance(values, list):
        return ()
    return tuple(sorted({value for value in values if isinstance(value, int) and value > 0}))


async def broadcast_recipients(draft: dict) -> tuple[int, int, tuple[int, ...] | None]:
    audience = draft.get("audience")
    if audience == "all":
        count, through_id = await get_broadcast_snapshot()
        return count, through_id, None
    if audience == "admins":
        ids = tuple(sorted(settings.admin_ids))
        return len(ids), 0, ids
    if audience == "selected":
        ids = selected_user_ids(draft)
        return len(ids), 0, ids
    return 0, 0, ()


async def show_user_selector(callback: CallbackQuery, state: FSMContext, language: str, requested_page: int) -> None:
    draft = await state.get_data()
    _, count = await get_broadcast_users_page(0, SELECTOR_PAGE_SIZE)
    if count == 0:
        await state.clear()
        await edit_screen(callback, translate("broadcast.no_users", language), broadcast_menu_keyboard(callback.from_user.id, language))
        return
    page = min(max(requested_page, 0), (count - 1) // SELECTOR_PAGE_SIZE)
    rows, _ = await get_broadcast_users_page(page * SELECTOR_PAGE_SIZE, SELECTOR_PAGE_SIZE)
    selected = set(selected_user_ids(draft))
    await state.update_data(selector_page=page)
    await edit_screen(
        callback,
        translate(
            "broadcast.select_users", language,
            selected=len(selected), limit=MAX_SELECTED_USERS, page=page + 1, pages=(count - 1) // SELECTOR_PAGE_SIZE + 1,
        ),
        broadcast_users_keyboard(callback.from_user.id, language, rows, selected, page, count, SELECTOR_PAGE_SIZE),
    )


async def show_broadcast_preview(message: Message, state: FSMContext, language: str) -> None:
    draft = await state.get_data()
    count, _, _ = await broadcast_recipients(draft)
    if count == 0:
        await state.clear()
        await message.answer(translate("broadcast.no_users", language), reply_markup=broadcast_menu_keyboard(message.from_user.id, language))
        return
    markup = broadcast_ad_keyboard(draft["button_text"], draft["url"]) if draft["kind"] == "ad" else None
    await message.answer(translate("broadcast.preview", language))
    try:
        await message.answer(draft["text"], reply_markup=markup)
    except TelegramBadRequest:
        await message.answer(translate("broadcast.preview_failed", language))
        return
    await state.set_state(AdminState.waiting_for_broadcast_confirmation)
    await message.answer(
        translate("broadcast.confirm", language, count=count, audience=translate(f"broadcast.audience_{draft['audience']}", language)),
        reply_markup=broadcast_confirm_keyboard(message.from_user.id, language),
    )


@router.callback_query(lambda query: (query.data or "").startswith("broadcast:"))
async def open_broadcast_menu(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await state.clear()
    count, _ = await get_broadcast_snapshot()
    await edit_screen(
        callback,
        translate("broadcast.menu", language, count=count),
        broadcast_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith(("broadcastnews:", "broadcastad:")))
async def start_broadcast_draft(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    kind = "ad" if data.action == "broadcastad" else "news"
    await state.clear()
    await state.set_state(AdminState.waiting_for_broadcast_audience)
    await state.update_data(kind=kind, selected_ids=[])
    await edit_screen(
        callback,
        translate("broadcast.audience_prompt", language),
        broadcast_audience_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("broadcastto:"))
async def choose_broadcast_audience(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    if await state.get_state() != AdminState.waiting_for_broadcast_audience.state or data.value not in {"all", "admins", "selected"}:
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    await state.update_data(audience=data.value)
    if data.value == "selected":
        await state.set_state(AdminState.waiting_for_broadcast_users)
        await show_user_selector(callback, state, language, 0)
    else:
        await state.set_state(AdminState.waiting_for_broadcast_text)
        await edit_screen(
            callback,
            translate("broadcast.text_prompt", language, limit=MAX_BROADCAST_TEXT_LENGTH),
            broadcast_cancel_keyboard(callback.from_user.id, language),
        )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("broadcastpage:"))
async def change_broadcast_user_page(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    if await state.get_state() != AdminState.waiting_for_broadcast_users.state:
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    page = int(data.value) if data.value and data.value.isdigit() else 0
    await show_user_selector(callback, state, language, page)
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("broadcastpick:"))
async def toggle_broadcast_user(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    if await state.get_state() != AdminState.waiting_for_broadcast_users.state or not data.value or not data.value.isdigit():
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    user_id = int(data.value)
    if not await broadcast_user_exists(user_id):
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    draft = await state.get_data()
    selected = set(selected_user_ids(draft))
    if user_id in selected:
        selected.remove(user_id)
    elif len(selected) >= MAX_SELECTED_USERS:
        await callback.answer(translate("broadcast.too_many_users", language, limit=MAX_SELECTED_USERS), show_alert=True)
        return
    else:
        selected.add(user_id)
    await state.update_data(selected_ids=sorted(selected))
    await show_user_selector(callback, state, language, int(draft.get("selector_page", 0)))
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("broadcastready:"))
async def finish_broadcast_users(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    if await state.get_state() != AdminState.waiting_for_broadcast_users.state:
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    if not selected_user_ids(await state.get_data()):
        await callback.answer(translate("broadcast.select_one", language), show_alert=True)
        return
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await edit_screen(
        callback,
        translate("broadcast.text_prompt", language, limit=MAX_BROADCAST_TEXT_LENGTH),
        broadcast_cancel_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.message(AdminState.waiting_for_broadcast_audience)
async def remind_broadcast_audience(message: Message) -> None:
    language = await authorize_broadcast_message(message)
    if language is not None:
        await message.answer(translate("broadcast.audience_prompt", language), reply_markup=broadcast_audience_keyboard(message.from_user.id, language))


@router.message(AdminState.waiting_for_broadcast_users)
async def remind_broadcast_users(message: Message) -> None:
    language = await authorize_broadcast_message(message)
    if language is not None:
        await message.answer(translate("broadcast.users_hint", language), reply_markup=broadcast_cancel_keyboard(message.from_user.id, language))


@router.message(AdminState.waiting_for_broadcast_text, F.text)
async def receive_broadcast_text(message: Message, state: FSMContext) -> None:
    language = await authorize_broadcast_message(message)
    if language is None:
        return
    text = message.text.strip()
    if not text or len(text) > MAX_BROADCAST_TEXT_LENGTH:
        await message.answer(translate("broadcast.invalid_text", language, limit=MAX_BROADCAST_TEXT_LENGTH))
        return
    draft = await state.get_data()
    await state.update_data(text=text)
    if draft.get("kind") == "ad":
        await state.set_state(AdminState.waiting_for_broadcast_button)
        await message.answer(
            translate("broadcast.button_prompt", language, limit=MAX_BUTTON_TEXT_LENGTH),
            reply_markup=broadcast_cancel_keyboard(message.from_user.id, language),
        )
    elif draft.get("kind") == "news":
        await show_broadcast_preview(message, state, language)
    else:
        await state.clear()
        await message.answer(translate("broadcast.expired", language))


@router.message(AdminState.waiting_for_broadcast_button, F.text)
async def receive_broadcast_button(message: Message, state: FSMContext) -> None:
    language = await authorize_broadcast_message(message)
    if language is None:
        return
    button_text = message.text.strip()
    if not button_text or len(button_text) > MAX_BUTTON_TEXT_LENGTH:
        await message.answer(translate("broadcast.invalid_button", language, limit=MAX_BUTTON_TEXT_LENGTH))
        return
    await state.update_data(button_text=button_text)
    await state.set_state(AdminState.waiting_for_broadcast_url)
    await message.answer(
        translate("broadcast.url_prompt", language),
        reply_markup=broadcast_cancel_keyboard(message.from_user.id, language),
    )


@router.message(AdminState.waiting_for_broadcast_url, F.text)
async def receive_broadcast_url(message: Message, state: FSMContext) -> None:
    language = await authorize_broadcast_message(message)
    if language is None:
        return
    url = message.text.strip()
    if not valid_button_url(url):
        await message.answer(translate("broadcast.invalid_url", language))
        return
    await state.update_data(url=url)
    await show_broadcast_preview(message, state, language)


@router.message(StateFilter(
    AdminState.waiting_for_broadcast_text,
    AdminState.waiting_for_broadcast_button,
    AdminState.waiting_for_broadcast_url,
))
async def reject_broadcast_attachment(message: Message) -> None:
    language = await authorize_broadcast_message(message)
    if language is not None:
        await message.answer(translate("broadcast.text_only", language))


@router.message(AdminState.waiting_for_broadcast_confirmation)
async def remind_broadcast_confirmation(message: Message) -> None:
    language = await authorize_broadcast_message(message)
    if language is not None:
        await message.answer(translate("broadcast.confirm_button", language))


@router.callback_query(lambda query: (query.data or "").startswith("broadcastcancel:"))
async def cancel_broadcast_draft(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await state.clear()
    count, _ = await get_broadcast_snapshot()
    await edit_screen(
        callback,
        translate("broadcast.menu", language, count=count),
        broadcast_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("broadcastsend:"))
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    authorized = await authorize_broadcast_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    if await state.get_state() != AdminState.waiting_for_broadcast_confirmation.state:
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    draft = await state.get_data()
    if draft.get("kind") not in {"news", "ad"} or draft.get("audience") not in {"all", "admins", "selected"} or not isinstance(draft.get("text"), str):
        await state.clear()
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    if draft["kind"] == "ad" and (not draft.get("button_text") or not valid_button_url(draft.get("url", ""))):
        await state.clear()
        await callback.answer(translate("broadcast.expired", language), show_alert=True)
        return
    if broadcast_lock.locked():
        await callback.answer(translate("broadcast.busy", language), show_alert=True)
        return
    await broadcast_lock.acquire()
    try:
        count, through_id, explicit_ids = await broadcast_recipients(draft)
        await state.clear()
        if count == 0:
            await callback.answer(translate("broadcast.no_users", language), show_alert=True)
            return
        await callback.answer()
        await edit_screen(callback, translate("broadcast.sending", language, count=count), broadcast_menu_keyboard(callback.from_user.id, language))
        markup = broadcast_ad_keyboard(draft["button_text"], draft["url"]) if draft["kind"] == "ad" else None
        result = await deliver_broadcast(
            bot, callback.from_user.id, draft["kind"], draft["text"], through_id, count,
            draft["audience"], explicit_ids, markup,
        )
        await bot.send_message(
            callback.from_user.id,
            translate(
                "broadcast.finished",
                language,
                sent=result.sent,
                unavailable=result.unavailable,
                failed=result.failed,
            ),
        )
    except Exception:
        logger.exception("Не удалось завершить рассылку администратора %s", callback.from_user.id)
        await bot.send_message(callback.from_user.id, translate("broadcast.failed", language))
    finally:
        broadcast_lock.release()
