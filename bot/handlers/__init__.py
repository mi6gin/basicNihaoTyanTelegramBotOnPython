from aiogram import Router

from bot.handlers import language, main_menu, support, users

router = Router(name="handlers")
router.include_routers(main_menu.router, language.router, support.router, users.router)
