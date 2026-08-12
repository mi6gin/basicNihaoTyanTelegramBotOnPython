from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import Callback
from localization import translate


def support_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("support.my_appeals", language), callback_data=Callback("appeals", user_id, "0").pack())],
        [InlineKeyboardButton(text=translate("support.report", language), callback_data=Callback("report", user_id).pack())],
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("main", user_id).pack())],
    ])


def appeals_keyboard(user_id: int, language: str, offset: int, count: int, appeal_id: int) -> InlineKeyboardMarkup:
    navigation = []
    if offset > 0:
        navigation.append(InlineKeyboardButton(text=translate("button.newer", language), callback_data=Callback("appeals", user_id, str(offset - 1)).pack()))
    if offset + 1 < count:
        navigation.append(InlineKeyboardButton(text=translate("button.older", language), callback_data=Callback("appeals", user_id, str(offset + 1)).pack()))
    buttons = [navigation] if navigation else []
    buttons.extend([
        [InlineKeyboardButton(text=translate("button.view", language), callback_data=Callback("appeal", user_id, str(appeal_id)).pack())],
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("support", user_id).pack())],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def appeal_keyboard(user_id: int, language: str, offset: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("appeals", user_id, str(offset)).pack())]
    ])


def cancel_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("cancel", user_id).pack())]
    ])


def created_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("support.my_appeals", language), callback_data=Callback("appeals", user_id, "0").pack())],
        [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("support", user_id).pack())],
    ])
