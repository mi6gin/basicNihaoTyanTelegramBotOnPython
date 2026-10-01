from aiogram import Router
from aiogram.types import CallbackQuery, Message

from nihao_tyan.telegram.common import authorize_callback, edit_screen
from nihao_tyan.telegram.keyboards.main_menu import main_menu_keyboard
from nihao_tyan.i18n import translate

router = Router(name="main_menu")


def main_menu_text(name: str, language: str, *, private_chat: bool = True) -> str:
    key = "main.welcome" if private_chat else "main.group_welcome"
    return translate(key, language, name=name)


async def send_main_menu(message: Message, language: str) -> None:
    if message.from_user is None:
        return
    private_chat = message.chat.type == "private"
    await message.answer(
        main_menu_text(message.from_user.first_name, language, private_chat=private_chat),
        reply_markup=main_menu_keyboard(message.from_user.id, language, private_chat=private_chat),
    )


@router.callback_query(lambda query: (query.data or "").startswith("main:"))
async def open_main_menu(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback, allow_group=True)
    if authorized is None:
        return
    language, _ = authorized
    private_chat = callback.message.chat.type == "private"
    await edit_screen(
        callback,
        main_menu_text(callback.from_user.first_name, language, private_chat=private_chat),
        main_menu_keyboard(callback.from_user.id, language, private_chat=private_chat),
    )
    await callback.answer()
