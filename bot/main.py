from aiogram import Bot, Dispatcher
from settings import settings
from handlers import (
    admin,
    basic,
    resume,
    speech,
    echo
)
import asyncio
import logging
from utils.commands import set_commands
from middlewares.typing import TypingMiddleware

logger = logging.getLogger(__name__)


async def start_bot(bot: Bot):
    await set_commands(bot)
    await bot.send_message(settings.bots.admin_id, text='Bot started!')


async def stop_bot(bot: Bot):
    await bot.send_message(settings.bots.admin_id, text='Bot stopped!')


async def start():
    bot = Bot(token=settings.bots.bot_token)
    dp = Dispatcher()

    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)

    dp.message.middleware.register(TypingMiddleware())

    dp.include_routers(
        speech.router,
        admin.router,
        basic.router,
        resume.router,
        echo.router
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    if settings.bots.debug:
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("Debugger enabled!")
    asyncio.run(start())
