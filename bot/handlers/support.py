import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.common import authorize_callback, edit_screen, sync_user
from bot.keyboards.support import appeal_keyboard, appeals_keyboard, cancel_keyboard, created_keyboard, support_keyboard
from bot.states import SupportState
from localization import translate
from settings import settings
from storage.appeals import create_appeal, get_appeal, get_appeal_at, get_appeal_offset

logger = logging.getLogger(__name__)
router = Router(name="support")


@router.callback_query(lambda query: (query.data or "").startswith("support:"))
async def open_support(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await edit_screen(callback, translate("support.menu", language), support_keyboard(callback.from_user.id, language))
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("appeals:"))
async def list_appeals(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    offset = int(data.value) if data.value and data.value.isdigit() else 0
    appeal, count = get_appeal_at(callback.from_user.id, offset)
    if appeal is None:
        await edit_screen(callback, translate("support.empty", language), support_keyboard(callback.from_user.id, language))
    else:
        status = translate("status.answered" if appeal.status else "status.new", language)
        created_at = datetime.fromisoformat(appeal.created_at).strftime("%d.%m.%Y %H:%M UTC")
        await edit_screen(
            callback,
            translate("support.list", language, number=appeal.id, status=status, created_at=created_at),
            appeals_keyboard(callback.from_user.id, language, offset, count, appeal.id),
        )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("appeal:"))
async def view_appeal(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    if not data.value or not data.value.isdigit():
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    appeal = get_appeal(callback.from_user.id, int(data.value))
    offset = get_appeal_offset(callback.from_user.id, int(data.value))
    if appeal is None or offset is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    status = translate("status.answered" if appeal.status else "status.new", language)
    answer = translate("support.answer", language, answer=appeal.answer) if appeal.status and appeal.answer else ""
    await edit_screen(
        callback,
        translate("support.view", language, number=appeal.id, text=appeal.text, status=status, answer=answer),
        appeal_keyboard(callback.from_user.id, language, offset),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("report:"))
async def request_appeal_text(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    if isinstance(callback.message, Message):
        await callback.message.delete()
        prompt = await callback.message.answer(translate("support.prompt", language), reply_markup=cancel_keyboard(callback.from_user.id, language))
        await state.set_state(SupportState.waiting_for_text)
        await state.update_data(prompt_message_id=prompt.message_id)
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("cancel:"))
async def cancel_appeal(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.delete()
        await bot.send_message(callback.from_user.id, translate("support.menu", language), reply_markup=support_keyboard(callback.from_user.id, language))
    await callback.answer()


@router.message(SupportState.waiting_for_text, F.text)
async def receive_appeal(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return
    language = sync_user(message.from_user)
    state_data = await state.get_data()
    await state.clear()
    prompt_message_id = state_data.get("prompt_message_id")
    if prompt_message_id:
        try:
            await bot.delete_message(message.chat.id, prompt_message_id)
        except TelegramBadRequest:
            pass
    appeal_id = create_appeal(message.from_user.id, message.text)
    await message.answer(translate("support.created", language, number=appeal_id), reply_markup=created_keyboard(message.from_user.id, language))
    full_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, translate("support.admin_notice", "ru", number=appeal_id, name=full_name, user_id=message.from_user.id, username=username, text=message.text))
        except Exception:
            logger.exception("Не удалось уведомить администратора %s об обращении %s", admin_id, appeal_id)


@router.message(SupportState.waiting_for_text)
async def reject_attachment(message: Message) -> None:
    if message.from_user is not None:
        await message.answer(translate("support.text_only", sync_user(message.from_user)))


@router.callback_query(lambda query: (query.data or "").startswith("admin:"))
async def admin_placeholder(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    key = "admin.later" if callback.from_user.id in settings.admin_ids else "admin.denied"
    await callback.answer(translate(key, language), show_alert=True)
