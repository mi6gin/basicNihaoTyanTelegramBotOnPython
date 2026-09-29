import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from sqlalchemy import text

from activity_log import AdminErrorHandler, MESSAGE_UPDATE_TYPES, IncomingUpdateMiddleware, JournalErrorHandler, configure_journal
from bot.commands import router as commands_router
from bot.handlers import router as handlers_router
from localization import translate
from settings import settings
from storage import create_database_engine, set_database_engine
from storage.fsm import PostgreSQLStorage

logger = logging.getLogger(__name__)


async def run_bot() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    configure_journal()
    bot = Bot(token=settings.bot_token)
    journal_errors = JournalErrorHandler()
    admin_errors = AdminErrorHandler(bot, settings.admin_ids)
    root_logger = logging.getLogger()
    root_logger.addHandler(journal_errors)
    root_logger.addHandler(admin_errors)
    engine = None
    try:
        engine = create_database_engine(settings.database_url)
        set_database_engine(engine)
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        dispatcher = Dispatcher(storage=PostgreSQLStorage(engine))
        dispatcher.update.outer_middleware(IncomingUpdateMiddleware())
        dispatcher.include_routers(commands_router, handlers_router)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=translate("command.start", "ru")),
                BotCommand(command="help", description=translate("command.help", "ru")),
            ],
        )
        for language in ("ru", "en"):
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description=translate("command.start", language)),
                    BotCommand(command="help", description=translate("command.help", language)),
                ],
                language_code=language,
            )
        await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
        allowed_updates = sorted(set(dispatcher.resolve_used_update_types()) | set(MESSAGE_UPDATE_TYPES) | {"my_chat_member"})
        await dispatcher.start_polling(bot, allowed_updates=allowed_updates)
    except Exception:
        logger.exception("Bot failed to start or stopped unexpectedly")
        raise
    finally:
        root_logger.removeHandler(admin_errors)
        root_logger.removeHandler(journal_errors)
        await admin_errors.shutdown()
        await bot.session.close()
        if engine is not None:
            await engine.dispose()
