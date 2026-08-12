from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import Callback
from localization import translate
from settings import settings


def main_menu_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=translate("main.support", language), callback_data=Callback("support", user_id).pack())],
        [InlineKeyboardButton(text=translate("main.language", language), callback_data=Callback("language", user_id).pack())],
    ]
    if user_id in settings.admin_ids:
        buttons.append([InlineKeyboardButton(text=translate("main.admin", language), callback_data=Callback("admin", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
