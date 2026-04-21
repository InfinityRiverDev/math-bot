"""
main.py  —  добавлен group_chat router
ИЗМЕНЕНИЯ: добавлен from handlers import group_chat и dp.include_router(group_chat.router)
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiohttp import web
from dotenv import load_dotenv

from handlers import user, admin, registration, profile
from handlers import schedule, lectures, attendance, billing
from handlers import group_chat                        # ← НОВЫЙ
from services import pomodoro

from middlewares.subscription_check import SubscriptionMiddleware
from handlers.billing import yookassa_webhook
from handlers import help as help_handler
from handlers import stats as stats_handler
from services import todo, music

load_dotenv()

TOKEN        = os.getenv("TOKEN")
PROXY        = os.getenv("PROXY")
WEBHOOK_PORT = int(os.getenv("PORT", 8080))

if not TOKEN:
    raise ValueError("❌ TOKEN не найден в .env")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
if not _admin_ids_raw:
    raise ValueError("❌ ADMIN_IDS не найден в .env")

if PROXY:
    session = AiohttpSession(proxy=PROXY)
else:
    session = AiohttpSession()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)

dp = Dispatcher()


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start",  description="🤖 Главное меню"),
        BotCommand(command="wallet", description="💼 Кошелёк"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help",   description="ℹ️ Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main():
    logging.basicConfig(level=logging.INFO)

    # ⚠️ Порядок важен — registration первым, group_chat последним
    dp.include_router(registration.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)
    dp.include_router(billing.router)
    dp.include_router(schedule.router)
    dp.include_router(lectures.router)
    dp.include_router(attendance.router)   # attendance до group_chat!
    dp.include_router(help_handler.router)
    dp.include_router(music.router)
    dp.include_router(stats_handler.router)
    dp.include_router(user.router)
    dp.include_router(pomodoro.router)
    dp.include_router(todo.router)
    dp.include_router(group_chat.router)   # ← ПОСЛЕДНИМ чтобы не перехватывал команды

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    await set_commands(bot)

    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/yookassa/webhook", yookassa_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT)
    await site.start()

    admin_ids = os.getenv("ADMIN_IDS", "")
    print(f"✅ aiohttp запущен на порту {WEBHOOK_PORT}")
    print(f"✅ Бот запущен!")
    print(f"✅ Групповой чат: включён")
    print(f"✅ Админы: {admin_ids}")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())