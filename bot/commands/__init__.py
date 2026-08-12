from aiogram import Router

from bot.commands import help, start

router = Router(name="commands")
router.include_routers(start.router, help.router)
