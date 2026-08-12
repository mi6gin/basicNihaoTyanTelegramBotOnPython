from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.common import sync_user
from bot.handlers.main_menu import send_main_menu

router = Router(name="start_command")


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    language = sync_user(message.from_user)
    await send_main_menu(message, language)
