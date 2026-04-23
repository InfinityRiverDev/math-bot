"""
main.py — Math Tutor Bot (Webhook mode для Render)
"""
import asyncio, logging, os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

from handlers import user, admin, registration, profile
from handlers import schedule, lectures, attendance, billing
from handlers import group_chat
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
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "")  # Render сам ставит эту переменную
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL  = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

if not TOKEN:
    raise ValueError("TOKEN не найден в .env")
if not os.getenv("ADMIN_IDS"):
    raise ValueError("ADMIN_IDS не найден в .env")

session = AiohttpSession(proxy=PROXY) if PROXY else AiohttpSession()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
dp  = Dispatcher()


async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start",  description="🤖 Главное меню"),
        BotCommand(command="wallet", description="💼 Кошелёк"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help",   description="ℹ️ Помощь"),
    ], scope=BotCommandScopeDefault())


def setup_routers():
    dp.include_router(registration.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)
    dp.include_router(billing.router)
    dp.include_router(schedule.router)
    dp.include_router(lectures.router)
    dp.include_router(attendance.router)
    dp.include_router(help_handler.router)
    dp.include_router(music.router)
    dp.include_router(stats_handler.router)
    dp.include_router(user.router)
    dp.include_router(pomodoro.router)
    dp.include_router(todo.router)
    dp.include_router(group_chat.router)  # ПОСЛЕДНИМ

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())


async def on_startup(bot: Bot):
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"]
    )
    await set_commands(bot)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.info("Webhook удалён")


async def main():
    logging.basicConfig(level=logging.INFO)

    setup_routers()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["bot"] = bot

    # Webhook для Telegram
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    # YooKassa webhook и healthcheck
    app.router.add_post("/yookassa/webhook", yookassa_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))

    setup_application(app, dp, bot=bot)

    print(f"✅ Бот запущен в webhook-режиме!")
    print(f"✅ URL: {WEBHOOK_URL}")
    print(f"✅ Порт: {WEBHOOK_PORT}")
    print(f"✅ Админы: {os.getenv('ADMIN_IDS')}")

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT).start()

    # Держим процесс живым
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())