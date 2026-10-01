from aiogram import Router

from nihao_tyan.telegram.commands import help, start

router = Router(name="commands")
router.include_routers(start.router, help.router)
