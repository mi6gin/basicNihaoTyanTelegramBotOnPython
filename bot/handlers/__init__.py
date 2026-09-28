from aiogram import Router

from bot.handlers import admin, language, main_menu, support, users

router = Router(name="handlers")
router.include_routers(main_menu.router, language.router, admin.router, support.router, users.router)
