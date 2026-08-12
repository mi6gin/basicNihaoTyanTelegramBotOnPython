from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot.common import authorize_callback, edit_screen
from bot.keyboards.main_menu import main_menu_keyboard
from localization import translate

router = Router(name="main_menu")


def main_menu_text(name: str, language: str) -> str:
    return translate("main.welcome", language, name=name)


async def send_main_menu(message: Message, language: str) -> None:
    if message.from_user is None:
        return
    await message.answer(
        main_menu_text(message.from_user.first_name, language),
        reply_markup=main_menu_keyboard(message.from_user.id, language),
    )


@router.callback_query(lambda query: (query.data or "").startswith("main:"))
async def open_main_menu(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await edit_screen(
        callback,
        main_menu_text(callback.from_user.first_name, language),
        main_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer()
