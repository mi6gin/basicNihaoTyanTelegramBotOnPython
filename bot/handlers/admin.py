import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from activity_log import TIMEZONE, get_journal, record_event
from bot.callbacks import Callback
from bot.common import authorize_callback, edit_screen, sync_user
from bot.constants import CATEGORIES, MAX_ANSWER_LENGTH
from bot.keyboards.admin import (
    admin_appeal_keyboard,
    admin_appeals_keyboard,
    admin_cancel_keyboard,
    admin_categories_keyboard,
    admin_directory_keyboard,
    admin_empty_category_keyboard,
    admin_log_entry_keyboard,
    admin_log_summary_keyboard,
    admin_logs_keyboard,
    admin_menu_keyboard,
)
from bot.keyboards.support import created_keyboard
from bot.presentation import appeal_category, appeal_status, format_dialog, format_journal_entry
from bot.states import AdminState
from localization import translate
from settings import settings
from storage.appeals import (
    answer_appeal,
    close_appeal,
    count_open_appeals_by_category,
    count_pending_appeals,
    get_admin_appeal,
    get_admin_appeal_at,
    get_appeal_messages,
)
from storage.chats import count_active_chats, get_chat_at
from storage.models import Appeal
from storage.users import get_user_at, get_user_language

logger = logging.getLogger(__name__)
router = Router(name="admin")


async def notify_user_about_answer(bot: Bot, appeal: Appeal, answer: str) -> bool:
    try:
        user_language = await get_user_language(appeal.user_id)
        await bot.send_message(
            appeal.user_id,
            translate("support.answer_notification", user_language, number=appeal.id, answer=answer),
            reply_markup=created_keyboard(appeal.user_id, user_language),
        )
        return True
    except Exception:
        logger.exception("Не удалось уведомить пользователя %s об ответе на обращение %s", appeal.user_id, appeal.id)
        return False


async def send_stored_attachment(bot: Bot, chat_id: int, content_type: str, file_id: str, caption: str) -> None:
    if content_type == "photo":
        await bot.send_photo(chat_id, file_id, caption=caption)
    elif content_type == "document":
        await bot.send_document(chat_id, file_id, caption=caption)


async def authorize_admin(callback: CallbackQuery) -> tuple[str, Callback] | None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return None
    language, data = authorized
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer(translate("admin.denied", language), show_alert=True)
        return None
    return language, data


def parse_list_position(value: str | None) -> tuple[str, int]:
    parts = (value or "pending.0").split(".")
    allowed = {"pending", "new", "all", *CATEGORIES, *(f"{category}_all" for category in CATEGORIES)}
    filter_name = parts[0] if parts[0] in allowed else "pending"
    offset = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return filter_name, offset


def parse_appeal_position(value: str | None) -> tuple[int, str, int] | None:
    parts = (value or "").split(".")
    if not parts or not parts[0].isdigit():
        return None
    allowed = {"pending", "new", "all", *CATEGORIES, *(f"{category}_all" for category in CATEGORIES)}
    filter_name = parts[1] if len(parts) > 1 and parts[1] in allowed else "all"
    offset = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return int(parts[0]), filter_name, offset


@router.callback_query(lambda query: (query.data or "").startswith("admin:"))
async def open_admin(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, _ = authorized
    await state.clear()
    await edit_screen(
        callback,
        translate("admin.menu", language, count=await count_pending_appeals()),
        admin_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminlogs:"))
async def list_daily_logs(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    journal = get_journal()
    if journal is None:
        await callback.answer(translate("admin.logs_unavailable", language), show_alert=True)
        return
    today = datetime.now(TIMEZONE).date()
    days = list(dict.fromkeys([today.isoformat(), (today - timedelta(days=1)).isoformat(), *journal.dates()]))
    requested_offset = int(data.value) if data.value and data.value.isdigit() else 0
    offset = min(requested_offset, max(0, ((len(days) - 1) // 7) * 7))
    await edit_screen(
        callback,
        translate("admin.logs_list", language, count=len(journal.dates())),
        admin_logs_keyboard(callback.from_user.id, language, days, offset),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminlog:"))
async def show_daily_log(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    journal = get_journal()
    if journal is None or not data.value:
        await callback.answer(translate("admin.logs_unavailable", language), show_alert=True)
        return
    try:
        summary = journal.summary(data.value)
    except ValueError:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    counts = summary["counts"]
    by_category = summary["categories"]
    category_lines = "\n".join(f"{appeal_category(category, language)}: {by_category[category]}" for category in CATEGORIES)
    await edit_screen(
        callback,
        translate(
            "admin.logs_summary",
            language,
            date=data.value,
            messages=counts["incoming_message"],
            users=summary["users"],
            chats=summary["chats"],
            created=counts["appeal_created"],
            followups=counts["appeal_followup"],
            answers=counts["appeal_answered"],
            closed=counts["appeal_closed"],
            errors=counts["error"],
            categories=category_lines,
        ),
        admin_log_summary_keyboard(callback.from_user.id, language, data.value, journal.file_path(data.value) is not None),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminlogentry:"))
async def show_journal_entry(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    journal = get_journal()
    if journal is None or not data.value:
        await callback.answer(translate("admin.logs_unavailable", language), show_alert=True)
        return
    day, separator, raw_offset = data.value.rpartition(".")
    if not separator or not raw_offset.isdigit():
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    offset = int(raw_offset)
    try:
        item, count = journal.entry(day, offset)
    except ValueError:
        item, count = None, 0
    if item is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    await edit_screen(
        callback,
        format_journal_entry(item, language, offset + 1, count),
        admin_log_entry_keyboard(callback.from_user.id, language, day, offset, count),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminlogfile:"))
async def send_daily_log_file(callback: CallbackQuery, bot: Bot) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    journal = get_journal()
    if journal is None or not data.value:
        await callback.answer(translate("admin.logs_unavailable", language), show_alert=True)
        return
    try:
        path = journal.file_path(data.value)
    except ValueError:
        path = None
    if path is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    if path.stat().st_size > 45 * 1024 * 1024:
        await callback.answer(translate("admin.log_too_large", language), show_alert=True)
        return
    await callback.answer()
    try:
        await bot.send_document(callback.from_user.id, FSInputFile(path, filename=path.name))
    except Exception:
        logger.exception("Не удалось отправить журнал за %s администратору %s", data.value, callback.from_user.id)
        await bot.send_message(callback.from_user.id, translate("admin.log_send_failed", language))


@router.callback_query(lambda query: (query.data or "").startswith("adminusers:"))
async def list_known_users(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    offset = int(data.value) if data.value and data.value.isdigit() else 0
    row, count = await get_user_at(offset)
    if row is None:
        text = translate("admin.users_empty", language)
    else:
        user_id, username, first_name, last_name, user_language, registered_at, last_seen_at = row
        name = " ".join(filter(None, [first_name, last_name]))
        text = translate(
            "admin.user_entry",
            language,
            position=offset + 1,
            count=count,
            name=name,
            username=f"@{username}" if username else "—",
            user_id=user_id,
            user_language=user_language,
            registered_at=datetime.fromisoformat(registered_at).astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
            last_seen_at=datetime.fromisoformat(last_seen_at or registered_at).astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
        )
    await edit_screen(callback, text, admin_directory_keyboard(callback.from_user.id, language, "adminusers", offset, count))
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("admingroups:"))
async def list_known_chats(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    offset = int(data.value) if data.value and data.value.isdigit() else 0
    row, count = await get_chat_at(offset)
    if row is None:
        text = translate("admin.chats_empty", language)
    else:
        chat_id, chat_type, title, username, bot_status, first_seen_at, last_seen_at = row
        text = translate(
            "admin.chat_entry",
            language,
            position=offset + 1,
            count=count,
            active=await count_active_chats(),
            title=title or "—",
            username=f"@{username}" if username else "—",
            chat_id=chat_id,
            chat_type=chat_type,
            status=translate("admin.chat_left" if bot_status in {"left", "kicked"} else "admin.chat_active", language),
            first_seen_at=datetime.fromisoformat(first_seen_at).astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
            last_seen_at=datetime.fromisoformat(last_seen_at).astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M"),
        )
    await edit_screen(callback, text, admin_directory_keyboard(callback.from_user.id, language, "admingroups", offset, count))
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminlist:"))
async def list_admin_appeals(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    filter_name, offset = parse_list_position(data.value)
    appeal, count = await get_admin_appeal_at(offset, filter_name)
    if appeal is None:
        text = translate("admin.empty_pending" if filter_name in {"pending", "new"} else "admin.empty", language)
        category = filter_name[:-4] if filter_name.endswith("_all") else filter_name
        if category in CATEGORIES:
            keyboard = admin_empty_category_keyboard(callback.from_user.id, language, filter_name)
        else:
            keyboard = admin_menu_keyboard(callback.from_user.id, language)
        await edit_screen(callback, text, keyboard)
    else:
        status = appeal_status(appeal, language)
        created_at = datetime.fromisoformat(appeal.created_at).strftime("%d.%m.%Y %H:%M UTC")
        await edit_screen(
            callback,
            translate(
                "admin.list",
                language,
                number=appeal.id,
                user_id=appeal.user_id,
                category=appeal_category(appeal.category, language),
                status=status,
                created_at=created_at,
                position=offset + 1,
                count=count,
            ),
            admin_appeals_keyboard(callback.from_user.id, language, offset, count, appeal.id, filter_name),
        )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("admincats:"))
async def list_admin_categories(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, _ = authorized
    await edit_screen(
        callback,
        translate("admin.choose_category", language),
        admin_categories_keyboard(callback.from_user.id, language, await count_open_appeals_by_category()),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminappeal:"))
async def view_admin_appeal(callback: CallbackQuery) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    position = parse_appeal_position(data.value)
    appeal = await get_admin_appeal(position[0]) if position else None
    if appeal is None or position is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    _, filter_name, offset = position
    status = appeal_status(appeal, language)
    messages = await get_appeal_messages(appeal.id)
    dialog = format_dialog(messages, language)
    await edit_screen(
        callback,
        translate(
            "admin.view",
            language,
            number=appeal.id,
            user_id=appeal.user_id,
            category=appeal_category(appeal.category, language),
            dialog=dialog,
            status=status,
        ),
        admin_appeal_keyboard(
            callback.from_user.id,
            language,
            appeal.id,
            filter_name,
            offset,
            appeal.workflow_status != "closed",
            any(message.file_id for message in messages),
        ),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("adminreply:"))
async def request_admin_answer(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    if not data.value or not data.value.isdigit():
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    appeal = await get_admin_appeal(int(data.value))
    if appeal is None or appeal.workflow_status == "closed":
        await callback.answer(translate("admin.already_answered", language), show_alert=True)
        return
    await edit_screen(
        callback,
        translate("admin.answer_prompt", language, number=appeal.id, limit=MAX_ANSWER_LENGTH),
        admin_cancel_keyboard(callback.from_user.id, language, appeal.id),
    )
    await state.set_state(AdminState.waiting_for_answer)
    await state.update_data(appeal_id=appeal.id, prompt_message_id=callback.message.message_id if isinstance(callback.message, Message) else None)
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("admincancel:"))
async def cancel_admin_answer(callback: CallbackQuery, state: FSMContext) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    await state.clear()
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    appeal = await get_admin_appeal(appeal_id)
    if appeal is None:
        await edit_screen(
            callback,
            translate("admin.menu", language, count=await count_pending_appeals()),
            admin_menu_keyboard(callback.from_user.id, language),
        )
    else:
        status = appeal_status(appeal, language)
        messages = await get_appeal_messages(appeal.id)
        dialog = format_dialog(messages, language)
        await edit_screen(
            callback,
            translate(
                "admin.view",
                language,
                number=appeal.id,
                user_id=appeal.user_id,
                category=appeal_category(appeal.category, language),
                dialog=dialog,
                status=status,
            ),
            admin_appeal_keyboard(
                callback.from_user.id,
                language,
                appeal.id,
                "all",
                0,
                appeal.workflow_status != "closed",
                any(message.file_id for message in messages),
            ),
        )
    await callback.answer()


@router.message(AdminState.waiting_for_answer, F.text)
async def receive_admin_answer(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return
    language = await sync_user(message.from_user)
    if message.chat.type != "private":
        await state.clear()
        await message.answer(translate("error.private_chat_only", language))
        return
    if message.from_user.id not in settings.admin_ids:
        await state.clear()
        await message.answer(translate("admin.denied", language))
        return
    answer_text = message.text.strip()
    if not answer_text:
        await message.answer(translate("admin.empty_answer", language))
        return
    if len(answer_text) > MAX_ANSWER_LENGTH:
        await message.answer(translate("admin.answer_too_long", language, limit=MAX_ANSWER_LENGTH))
        return
    state_data = await state.get_data()
    appeal_id = state_data.get("appeal_id")
    appeal = await answer_appeal(appeal_id, answer_text, message.from_user.id) if isinstance(appeal_id, int) else None
    await state.clear()
    if appeal is None:
        await message.answer(translate("admin.already_answered", language), reply_markup=admin_menu_keyboard(message.from_user.id, language))
        return
    record_event("appeal_answered", appeal_id=appeal.id, admin_id=message.from_user.id, user_id=appeal.user_id, category=appeal.category)
    prompt_message_id = state_data.get("prompt_message_id")
    if prompt_message_id:
        try:
            await bot.delete_message(message.chat.id, prompt_message_id)
        except TelegramBadRequest:
            pass
    notification_sent = await notify_user_about_answer(bot, appeal, answer_text)
    result_key = "admin.answer_saved" if notification_sent else "admin.answer_saved_no_notification"
    await message.answer(
        translate(result_key, language, number=appeal.id),
        reply_markup=admin_menu_keyboard(message.from_user.id, language),
    )


@router.message(AdminState.waiting_for_answer)
async def reject_admin_attachment(message: Message) -> None:
    if message.from_user is not None:
        await message.answer(translate("admin.text_only", await sync_user(message.from_user)))


@router.callback_query(lambda query: (query.data or "").startswith("adminclose:"))
async def close_admin_appeal(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    appeal = await close_appeal(appeal_id)
    if appeal is None:
        await callback.answer(translate("support.closed", language), show_alert=True)
        return
    record_event("appeal_closed", appeal_id=appeal.id, admin_id=callback.from_user.id, user_id=appeal.user_id, closed_by="admin", category=appeal.category)
    await state.clear()
    try:
        user_language = await get_user_language(appeal.user_id)
        await bot.send_message(
            appeal.user_id,
            translate("support.closed_by_admin", user_language, number=appeal.id),
            reply_markup=created_keyboard(appeal.user_id, user_language),
        )
    except Exception:
        logger.exception("Не удалось уведомить пользователя %s о закрытии обращения %s", appeal.user_id, appeal.id)
    await edit_screen(
        callback,
        translate("admin.menu", language, count=await count_pending_appeals()),
        admin_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer(translate("admin.closed", language))


@router.callback_query(lambda query: (query.data or "").startswith("adminfiles:"))
async def send_admin_attachments(callback: CallbackQuery, bot: Bot) -> None:
    authorized = await authorize_admin(callback)
    if authorized is None:
        return
    language, data = authorized
    appeal_id = int(data.value) if data.value and data.value.isdigit() else 0
    appeal = await get_admin_appeal(appeal_id)
    if appeal is None:
        await callback.answer(translate("error.not_found", language), show_alert=True)
        return
    attachments = [message for message in await get_appeal_messages(appeal.id, limit=50) if message.file_id]
    for item in attachments:
        await send_stored_attachment(bot, callback.from_user.id, item.content_type, item.file_id, item.text)
    await callback.answer(translate("support.attachments_sent", language, count=len(attachments)))
