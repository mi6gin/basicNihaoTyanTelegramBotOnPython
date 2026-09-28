import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from activity_log import record_event
from bot.common import authorize_callback, edit_screen, sync_user
from bot.constants import CATEGORIES, MAX_APPEAL_LENGTH
from bot.keyboards.admin import admin_notice_keyboard
from bot.keyboards.support import appeal_keyboard, appeals_keyboard, cancel_keyboard, category_keyboard, created_keyboard, support_keyboard
from bot.presentation import appeal_category, appeal_status, format_dialog
from bot.states import SupportState
from localization import translate
from settings import settings
from storage.appeals import (
    add_user_message,
    close_appeal,
    create_appeal,
    get_appeal,
    get_appeal_at,
    get_appeal_messages,
    get_appeal_offset,
)
from storage.users import get_user_language

logger = logging.getLogger(__name__)
router = Router(name="support")


def message_content(message: Message, language: str) -> tuple[str, str, str | None, str | None] | None:
    if message.text is not None:
        return message.text.strip(), "text", None, None
    if message.photo:
        return (message.caption or translate("attachment.photo", language)).strip(), "photo", message.photo[-1].file_id, None
    if message.document:
        file_name = message.document.file_name or translate("attachment.document", language)
        return (message.caption or file_name).strip(), "document", message.document.file_id, file_name
    return None


async def send_attachment(bot: Bot, chat_id: int, content_type: str, file_id: str | None, caption: str | None = None) -> None:
    if not file_id:
        return
    if content_type == "photo":
        await bot.send_photo(chat_id, file_id, caption=caption)
    elif content_type == "document":
        await bot.send_document(chat_id, file_id, caption=caption)


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
    appeal, count = await get_appeal_at(callback.from_user.id, offset)
    if appeal is None:
        await edit_screen(callback, translate("support.empty", language), support_keyboard(callback.from_user.id, language))
    else:
        status = appeal_status(appeal, language)
        created_at = datetime.fromisoformat(appeal.created_at).strftime("%d.%m.%Y %H:%M UTC")
        await edit_screen(
            callback,
            translate(
                "support.list",
                language,
                number=appeal.id,
                category=appeal_category(appeal.category, language),
                status=status,
                created_at=created_at,
            ),
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
    appeal = await get_appeal(callback.from_user.id, int(data.value))
    offset = await get_appeal_offset(callback.from_user.id, int(data.value))
    if appeal is None or offset is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    status = appeal_status(appeal, language)
    messages = await get_appeal_messages(appeal.id)
    dialog = format_dialog(messages, language)
    await edit_screen(
        callback,
        translate(
            "support.view",
            language,
            number=appeal.id,
            category=appeal_category(appeal.category, language),
            dialog=dialog,
            status=status,
        ),
        appeal_keyboard(
            callback.from_user.id,
            language,
            offset,
            appeal.id,
            appeal.workflow_status == "closed",
            any(message.file_id for message in messages),
        ),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("report:"))
async def request_appeal_text(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await state.clear()
    await edit_screen(
        callback,
        translate("support.choose_category", language),
        category_keyboard(callback.from_user.id, language),
    )
    await state.set_state(SupportState.waiting_for_category)
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("category:"))
async def choose_appeal_category(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    if data.value not in CATEGORIES:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    await edit_screen(
        callback,
        translate("support.prompt", language, category=appeal_category(data.value, language), limit=MAX_APPEAL_LENGTH),
        cancel_keyboard(callback.from_user.id, language),
    )
    await state.set_state(SupportState.waiting_for_text)
    await state.update_data(
        category=data.value,
        prompt_message_id=callback.message.message_id if isinstance(callback.message, Message) else None,
    )
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


@router.message(SupportState.waiting_for_text)
async def receive_appeal(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    language = await sync_user(message.from_user)
    content = message_content(message, language)
    if content is None:
        await message.answer(translate("support.unsupported_attachment", language))
        return
    appeal_text, content_type, file_id, file_name = content
    if not appeal_text:
        await message.answer(translate("support.empty_text", language))
        return
    if len(appeal_text) > MAX_APPEAL_LENGTH:
        await message.answer(translate("support.too_long", language, limit=MAX_APPEAL_LENGTH))
        return
    state_data = await state.get_data()
    category = state_data.get("category")
    if category not in CATEGORIES:
        await state.clear()
        await message.answer(translate("support.choose_category_again", language), reply_markup=support_keyboard(message.from_user.id, language))
        return
    appeal_id = await create_appeal(message.from_user.id, appeal_text, content_type, file_id, file_name, category)
    record_event("appeal_created", appeal_id=appeal_id, user_id=message.from_user.id, category=category, content_type=content_type)
    await state.clear()
    prompt_message_id = state_data.get("prompt_message_id")
    if prompt_message_id:
        try:
            await bot.delete_message(message.chat.id, prompt_message_id)
        except TelegramBadRequest:
            pass
    await message.answer(
        translate("support.created", language, number=appeal_id, category=appeal_category(category, language)),
        reply_markup=created_keyboard(message.from_user.id, language),
    )
    full_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    for admin_id in settings.admin_ids:
        try:
            admin_language = await get_user_language(admin_id)
            await bot.send_message(
                admin_id,
                translate(
                    "support.admin_notice",
                    admin_language,
                    number=appeal_id,
                    name=full_name,
                    user_id=message.from_user.id,
                    username=username,
                    text=appeal_text,
                    category=appeal_category(category, admin_language),
                ),
                reply_markup=admin_notice_keyboard(admin_id, appeal_id, admin_language),
            )
            await send_attachment(bot, admin_id, content_type, file_id)
        except Exception:
            logger.exception("Не удалось уведомить администратора %s об обращении %s", admin_id, appeal_id)


@router.callback_query(lambda query: (query.data or "").startswith("addmsg:"))
async def request_followup(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    appeal = await get_appeal(callback.from_user.id, appeal_id)
    if appeal is None or appeal.workflow_status == "closed":
        await callback.answer(translate("support.closed", language), show_alert=True)
        return
    await edit_screen(
        callback,
        translate("support.followup_prompt", language, number=appeal.id, limit=MAX_APPEAL_LENGTH),
        cancel_keyboard(callback.from_user.id, language),
    )
    await state.set_state(SupportState.waiting_for_followup)
    await state.update_data(appeal_id=appeal.id)
    await callback.answer()


@router.message(SupportState.waiting_for_followup)
async def receive_followup(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    language = await sync_user(message.from_user)
    content = message_content(message, language)
    if content is None:
        await message.answer(translate("support.unsupported_attachment", language))
        return
    text, content_type, file_id, file_name = content
    if not text:
        await message.answer(translate("support.empty_text", language))
        return
    if len(text) > MAX_APPEAL_LENGTH:
        await message.answer(translate("support.too_long", language, limit=MAX_APPEAL_LENGTH))
        return
    state_data = await state.get_data()
    appeal_id = state_data.get("appeal_id")
    appeal = await add_user_message(message.from_user.id, appeal_id, text, content_type, file_id, file_name) if isinstance(appeal_id, int) else None
    if appeal is None:
        await state.clear()
        await message.answer(translate("support.closed", language), reply_markup=support_keyboard(message.from_user.id, language))
        return
    record_event("appeal_followup", appeal_id=appeal.id, user_id=message.from_user.id, category=appeal.category, content_type=content_type)
    await state.clear()
    await message.answer(
        translate("support.followup_saved", language, number=appeal.id),
        reply_markup=created_keyboard(message.from_user.id, language),
    )
    for admin_id in settings.admin_ids:
        try:
            admin_language = await get_user_language(admin_id)
            await bot.send_message(
                admin_id,
                translate("support.admin_followup", admin_language, number=appeal.id, user_id=appeal.user_id, text=text),
                reply_markup=admin_notice_keyboard(admin_id, appeal.id, admin_language),
            )
            await send_attachment(bot, admin_id, content_type, file_id)
        except Exception:
            logger.exception("Не удалось уведомить администратора %s о дополнении обращения %s", admin_id, appeal.id)


@router.callback_query(lambda query: (query.data or "").startswith("closeappeal:"))
async def close_user_appeal(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    existing = await get_appeal(callback.from_user.id, appeal_id)
    appeal = await close_appeal(appeal_id) if existing and existing.workflow_status != "closed" else None
    if appeal is None:
        await callback.answer(translate("support.closed", language), show_alert=True)
        return
    record_event("appeal_closed", appeal_id=appeal.id, user_id=callback.from_user.id, closed_by="user", category=appeal.category)
    await state.clear()
    messages = await get_appeal_messages(appeal.id)
    dialog = format_dialog(messages, language)
    await edit_screen(
        callback,
        translate(
            "support.view",
            language,
            number=appeal.id,
            category=appeal_category(appeal.category, language),
            dialog=dialog,
            status=appeal_status(appeal, language),
        ),
        appeal_keyboard(callback.from_user.id, language, 0, appeal.id, True, any(message.file_id for message in messages)),
    )
    await callback.answer(translate("support.closed_success", language))


@router.callback_query(lambda query: (query.data or "").startswith("files:"))
async def send_user_attachments(callback: CallbackQuery, bot: Bot) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, data = authorized
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    appeal = await get_appeal(callback.from_user.id, appeal_id)
    if appeal is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    attachments = [message for message in await get_appeal_messages(appeal.id, limit=50) if message.file_id]
    for item in attachments:
        await send_attachment(bot, callback.from_user.id, item.content_type, item.file_id, item.text)
    await callback.answer(translate("support.attachments_sent", language, count=len(attachments)))
