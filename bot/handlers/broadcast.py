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
    broadcast_cancel_keyboard,
    broadcast_confirm_keyboard,
    broadcast_menu_keyboard,
)
from bot.states import AdminState
from localization import translate
from settings import settings
from storage.users import get_broadcast_snapshot

logger = logging.getLogger(__name__)
router = Router(name="broadcast")
MAX_BROADCAST_TEXT_LENGTH = 4000
MAX_BUTTON_TEXT_LENGTH = 64
MAX_BUTTON_URL_LENGTH = 2048


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


async def show_broadcast_preview(message: Message, state: FSMContext, language: str) -> None:
    draft = await state.get_data()
    count, _ = await get_broadcast_snapshot()
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
        translate("broadcast.confirm", language, count=count),
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
    await state.set_state(AdminState.waiting_for_broadcast_text)
    await state.update_data(kind=kind)
    await edit_screen(
        callback,
        translate("broadcast.text_prompt", language, limit=MAX_BROADCAST_TEXT_LENGTH),
        broadcast_cancel_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


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
    if draft.get("kind") not in {"news", "ad"} or not isinstance(draft.get("text"), str):
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
        count, through_id = await get_broadcast_snapshot()
        await state.clear()
        if count == 0:
            await callback.answer(translate("broadcast.no_users", language), show_alert=True)
            return
        await callback.answer()
        await edit_screen(callback, translate("broadcast.sending", language, count=count), broadcast_menu_keyboard(callback.from_user.id, language))
        markup = broadcast_ad_keyboard(draft["button_text"], draft["url"]) if draft["kind"] == "ad" else None
        result = await deliver_broadcast(bot, callback.from_user.id, draft["kind"], draft["text"], through_id, count, markup)
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
