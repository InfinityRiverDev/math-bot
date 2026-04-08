import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Роутеры (логика бота)
from handlers import user, admin, registration, profile
from services import pomodoro




# =========================
# 🔧 Загрузка конфигурации
# =========================
load_dotenv()

TOKEN = os.getenv("TOKEN")
PROXY = os.getenv("PROXY")

if not TOKEN:
    raise ValueError("❌ TOKEN не найден в .env")


# =========================
# 🌐 Настройка подключения (прокси / без)
# =========================
if PROXY:
    print(f"🌐 Использую прокси: {PROXY}")
    session = AiohttpSession(proxy=PROXY)
else:
    print("🌐 Запуск без прокси")
    session = AiohttpSession()


# =========================
# 🤖 Инициализация бота и диспетчера
# =========================
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)

dp = Dispatcher()


# =========================
# 📜 Команды бота (/start, /help и т.д.)
# =========================
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🤖 Главное меню"),
        BotCommand(command="cancel", description="🚫 Отмена"),
        BotCommand(command="help", description="ℹ️ Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


# =========================
# 🚀 Основная функция запуска
# =========================
async def main():
    logging.basicConfig(level=logging.INFO)

    # ⚠️ Порядок роутеров ВАЖЕН
    # registration — перехватывает /start для новых пользователей
    dp.include_router(registration.router)

    # профиль (работа с данными пользователя)
    dp.include_router(profile.router)

    # админка
    dp.include_router(admin.router)

    # основной пользовательский функционал (ИИ, калькулятор и т.д.)
    dp.include_router(user.router)

    # таймер помодоро
    dp.include_router(pomodoro.router)

    # 📜 Установка команд в Telegram
    await set_commands(bot)

    print("✅ Бот запущен!")

    print("✅ MongoDB подключена!")

    # ▶️ Запуск бота
    await dp.start_polling(bot)


# =========================
# ▶️ Точка входа
# =========================
if __name__ == "__main__":
    asyncio.run(main())