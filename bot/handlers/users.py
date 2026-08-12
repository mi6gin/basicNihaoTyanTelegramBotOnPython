from aiogram import Router
from aiogram.types import Message

from bot.common import sync_user

router = Router(name="users")


@router.message()
async def register_user(message: Message) -> None:
    if message.from_user is not None:
        sync_user(message.from_user)
