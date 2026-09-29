from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User

from bot.callbacks import Callback
from localization import telegram_language, translate
from storage.users import save_user


async def sync_user(user: User) -> str:
    return await save_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        initial_language=telegram_language(user.language_code),
    )


async def authorize_callback(callback: CallbackQuery, *, allow_group: bool = False) -> tuple[str, Callback] | None:
    language = await sync_user(callback.from_user)
    data = Callback.unpack(callback.data)
    if data is None or data.owner_id != callback.from_user.id:
        await callback.answer(translate("error.foreign_menu", language), show_alert=True)
        return None
    if not isinstance(callback.message, Message):
        await callback.answer(translate("error.private_chat_only", language), show_alert=True)
        return None
    chat_type = callback.message.chat.type
    if chat_type != "private" and not (
        allow_group and chat_type in {"group", "supergroup"} and data.action in {"main", "language", "setlang"}
    ):
        await callback.answer(translate("error.private_chat_only", language), show_alert=True)
        return None
    return language, data


async def edit_screen(
    callback: CallbackQuery,
    screen_text: str,
    keyboard: InlineKeyboardMarkup,
) -> int | None:
    if not isinstance(callback.message, Message):
        return None
    try:
        edited = await callback.message.edit_text(screen_text, reply_markup=keyboard)
        return edited.message_id
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            sent = await callback.message.answer(screen_text, reply_markup=keyboard)
            return sent.message_id
        return callback.message.message_id
