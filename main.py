# import asyncio
# import logging
# import os
#
# from aiogram import Bot, Dispatcher
# from aiogram.types import BotCommand, BotCommandScopeDefault
# from aiogram.client.default import DefaultBotProperties
# from aiogram.client.session.aiohttp import AiohttpSession
# from aiogram.enums import ParseMode
# from dotenv import load_dotenv
# from handlers import user, admin
# from database.models import db_start
#
# load_dotenv()
#
# #Прием, Ислам!
#
# session = AiohttpSession(proxy="socks5://127.0.0.1:12334")
# bot = Bot(token=os.getenv('TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
# dp = Dispatcher()
#
#
# async def set_commands(bot: Bot):
#     commands = [
#         BotCommand(
#             command="start",
#             description="🤖 Главное меню"
#         ),
#         BotCommand(
#             command="cancel",
#             description="🚫 Отмена текущего диалога"
#         ),
#         BotCommand(
#             command="help",
#             description="ℹ️ Помощь"
#         )
#     ]
#
#     await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
#
#
# logging.basicConfig(level=logging.INFO)
# # logging.getLogger('aiogram').disabled = True # выключить логирование
#
# async def main():
#     dp.include_router(admin.router)
#     dp.include_router(user.router)
#     await db_start()
#     await set_commands(bot)
#     await dp.start_polling(bot)
#
#
# if __name__ == '__main__':
#     asyncio.run(main())

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from handlers import user, admin
from database.models import db_start

load_dotenv()

TOKEN = os.getenv("TOKEN")
PROXY = os.getenv("PROXY")

if not TOKEN:
    raise ValueError("❌ TOKEN не найден в .env")

# 👇 ВОТ ГЛАВНАЯ МАГИЯ
if PROXY:
    print(f"🌐 Использую прокси: {PROXY}")
    session = AiohttpSession(proxy=PROXY)
else:
    print("🌐 Запуск без прокси")
    session = AiohttpSession()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)

dp = Dispatcher()


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🤖 Главное меню"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main():
    logging.basicConfig(level=logging.INFO)

    dp.include_router(admin.router)
    dp.include_router(user.router)

    await db_start()
    await set_commands(bot)

    print("✅ Бот запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())