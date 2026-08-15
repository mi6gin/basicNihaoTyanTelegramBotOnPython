import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot.commands import router as commands_router
from bot.handlers import router as handlers_router
from localization import translate
from settings import settings
from storage import USERS_DATABASE, initialize_storage
from storage.fsm import SQLiteStorage


async def run_bot() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    initialize_storage()
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher(storage=SQLiteStorage(USERS_DATABASE))
    dispatcher.include_routers(commands_router, handlers_router)
    for language in ("ru", "en"):
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=translate("command.start", language)),
                BotCommand(command="help", description=translate("command.help", language)),
            ],
            language_code=language,
        )
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
