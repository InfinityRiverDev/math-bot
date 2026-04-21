"""
main.py  —  бот Math Tutor
ИЗМЕНЕНИЯ: добавлен group_chat.router (включать ПОСЛЕДНИМ)
"""
import asyncio, logging, os
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiohttp import web
from dotenv import load_dotenv

from handlers import user, admin, registration, profile
from handlers import schedule, lectures, attendance, billing
from handlers import group_chat                 # ← НОВЫЙ
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
    raise ValueError("TOKEN не найден в .env")
if not os.getenv("ADMIN_IDS"):
    raise ValueError("ADMIN_IDS не найден в .env")

session = AiohttpSession(proxy=PROXY) if PROXY else AiohttpSession()

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)
dp = Dispatcher()


async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start",  description="🤖 Главное меню"),
        BotCommand(command="wallet", description="💼 Кошелёк"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help",   description="ℹ️ Помощь"),
    ], scope=BotCommandScopeDefault())


async def main():
    logging.basicConfig(level=logging.INFO)

    # ПОРЯДОК ВАЖЕН:
    # 1. registration — первым (перехватывает /start для новых)
    # 2. attendance — до group_chat (обрабатывает ссылки посещаемости в группах)
    # 3. group_chat — последним (не перехватывает команды)
    dp.include_router(registration.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)
    dp.include_router(billing.router)
    dp.include_router(schedule.router)
    dp.include_router(lectures.router)
    dp.include_router(attendance.router)      # ← до group_chat
    dp.include_router(help_handler.router)
    dp.include_router(music.router)
    dp.include_router(stats_handler.router)
    dp.include_router(user.router)
    dp.include_router(pomodoro.router)
    dp.include_router(todo.router)
    dp.include_router(group_chat.router)      # ← последним

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    await set_commands(bot)

    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/yookassa/webhook", yookassa_webhook)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT).start()

    print(f"✅ Бот запущен! Порт: {WEBHOOK_PORT}")
    print(f"✅ Групповой чат: включён (управление через админ-панель)")
    print(f"✅ Админы: {os.getenv('ADMIN_IDS')}")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())