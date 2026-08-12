from aiogram import Router
from aiogram.types import CallbackQuery

from bot.common import authorize_callback, edit_screen
from bot.keyboards.language import language_keyboard
from bot.keyboards.main_menu import main_menu_keyboard
from localization import SUPPORTED_LANGUAGES, translate
from storage.users import set_user_language

router = Router(name="language")


@router.callback_query(lambda query: (query.data or "").startswith("language:"))
async def choose_language(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    language, _ = authorized
    await edit_screen(
        callback,
        translate("language.choose", language),
        language_keyboard(callback.from_user.id, language),
    )
    await callback.answer()


@router.callback_query(lambda query: (query.data or "").startswith("setlang:"))
async def change_language(callback: CallbackQuery) -> None:
    authorized = await authorize_callback(callback)
    if authorized is None:
        return
    _, data = authorized
    if data.value not in SUPPORTED_LANGUAGES:
        await callback.answer()
        return
    language = data.value
    set_user_language(callback.from_user.id, language)
    await edit_screen(
        callback,
        translate("main.welcome", language, name=callback.from_user.first_name),
        main_menu_keyboard(callback.from_user.id, language),
    )
    await callback.answer()
