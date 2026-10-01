from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from nihao_tyan.telegram.callbacks import Callback
from nihao_tyan.i18n import translate
from nihao_tyan.config import settings


def main_menu_keyboard(user_id: int, language: str, *, private_chat: bool = True) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=translate("main.support", language), callback_data=Callback("support", user_id).pack())],
        [InlineKeyboardButton(text=translate("main.language", language), callback_data=Callback("language", user_id).pack())],
    ]
    if private_chat and user_id in settings.admin_ids:
        buttons.append([InlineKeyboardButton(text=translate("main.admin", language), callback_data=Callback("admin", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
