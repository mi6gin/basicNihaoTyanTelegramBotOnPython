from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import Callback
from bot.constants import CATEGORIES
from localization import translate


def support_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("support.my_appeals", language), callback_data=Callback("appeals", user_id, "0").pack())],
            [InlineKeyboardButton(text=translate("support.report", language), callback_data=Callback("report", user_id).pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("main", user_id).pack())],
        ]
    )


def category_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=translate(f"category.{category}", language),
                callback_data=Callback("category", user_id, category).pack(),
            )
        ]
        for category in CATEGORIES
    ]
    buttons.append([InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("cancel", user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def appeals_keyboard(user_id: int, language: str, offset: int, count: int, appeal_id: int) -> InlineKeyboardMarkup:
    navigation = []
    if offset > 0:
        navigation.append(InlineKeyboardButton(text=translate("button.newer", language), callback_data=Callback("appeals", user_id, str(offset - 1)).pack()))
    if offset + 1 < count:
        navigation.append(InlineKeyboardButton(text=translate("button.older", language), callback_data=Callback("appeals", user_id, str(offset + 1)).pack()))
    buttons = [navigation] if navigation else []
    buttons.extend(
        [
            [InlineKeyboardButton(text=translate("button.view", language), callback_data=Callback("appeal", user_id, str(appeal_id)).pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("support", user_id).pack())],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def appeal_keyboard(
    user_id: int,
    language: str,
    offset: int,
    appeal_id: int,
    is_closed: bool,
    has_attachments: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []
    if has_attachments:
        buttons.append([InlineKeyboardButton(text=translate("support.attachments", language), callback_data=Callback("files", user_id, str(appeal_id)).pack())])
    if not is_closed:
        buttons.extend(
            [
                [InlineKeyboardButton(text=translate("support.add_message", language), callback_data=Callback("addmsg", user_id, str(appeal_id)).pack())],
                [InlineKeyboardButton(text=translate("support.close", language), callback_data=Callback("closeappeal", user_id, str(appeal_id)).pack())],
            ]
        )
    buttons.append([InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("appeals", user_id, str(offset)).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=translate("button.cancel", language), callback_data=Callback("cancel", user_id).pack())]]
    )


def created_keyboard(user_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translate("support.my_appeals", language), callback_data=Callback("appeals", user_id, "0").pack())],
            [InlineKeyboardButton(text=translate("button.back", language), callback_data=Callback("support", user_id).pack())],
        ]
    )


def rating_keyboard(user_id: int, appeal_id: int, language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=translate("support.rating_yes", language), callback_data=Callback("rateappeal", user_id, f"{appeal_id}.1").pack()),
                InlineKeyboardButton(text=translate("support.rating_no", language), callback_data=Callback("rateappeal", user_id, f"{appeal_id}.-1").pack()),
            ],
            [InlineKeyboardButton(text=translate("support.my_appeals", language), callback_data=Callback("appeals", user_id, "0").pack())],
        ]
    )
