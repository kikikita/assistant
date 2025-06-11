from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_commands(bot: Bot):
    commands = [
        BotCommand(
            command='start',
            description='Start bot'
        ),
        BotCommand(
            command='help',
            description='Show help'
        ),
        BotCommand(
            command='insights',
            description='Show insights about user'
        ),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())
