"""
main.py

ИЗМЕНЕНИЯ:
- Добавлены роутеры: schedule, lectures, attendance, billing
- Добавлен SubscriptionMiddleware
- Добавлен aiohttp-сервер для вебхука ЮKassa
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
from services import pomodoro

from middlewares.subscription_check import SubscriptionMiddleware
from handlers.billing import yookassa_webhook

load_dotenv()

TOKEN        = os.getenv("TOKEN")
PROXY        = os.getenv("PROXY")
WEBHOOK_PORT = int(os.getenv("PORT", 8080))

if not TOKEN:
    raise ValueError("❌ TOKEN не найден в .env")

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
        BotCommand(command="start",  description="🤖 Главное меню"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help",   description="ℹ️ Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main():
    logging.basicConfig(level=logging.INFO)

    # ⚠️ Порядок роутеров важен
    dp.include_router(registration.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)
    dp.include_router(billing.router)       # ⬅️ кошелёк и оплата
    dp.include_router(schedule.router)
    dp.include_router(lectures.router)
    dp.include_router(attendance.router)
    dp.include_router(user.router)
    dp.include_router(pomodoro.router)

    # ⬅️ Middleware проверки подписки (после регистрации роутеров)
    dp.update.middleware(SubscriptionMiddleware())

    await set_commands(bot)

    # ⬅️ aiohttp-сервер для вебхука ЮKassa
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/yookassa/webhook", yookassa_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT)
    await site.start()
    print(f"✅ aiohttp запущен на порту {WEBHOOK_PORT}")

    print("✅ Бот запущен!")
    print("✅ MongoDB подключена!")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())