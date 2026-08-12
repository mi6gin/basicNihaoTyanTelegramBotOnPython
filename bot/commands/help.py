from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.common import sync_user
from localization import translate

router = Router(name="help_command")


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    if message.from_user is None:
        return
    language = sync_user(message.from_user)
    await message.answer(translate("help.text", language))
