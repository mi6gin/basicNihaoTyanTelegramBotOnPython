from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import Callback
from localization import translate


def language_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=translate("language.ru", language), callback_data=Callback("setlang", user_id, "ru").pack()),
            InlineKeyboardButton(text=translate("language.en", language), callback_data=Callback("setlang", user_id, "en").pack()),
        ],
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("main", user_id).pack())],
    ])
