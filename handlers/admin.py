import asyncio
import os

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv

from database.models import count_users, get_all_users
import keyboards.user_kb as kb


# =========================
# 🔧 Конфигурация
# =========================
load_dotenv()

router = Router()

# Список администраторов (из .env)
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS").split(",")))


# =========================
# 🛡️ Проверка на админа
# =========================
def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


# =========================
# ⚙️ Главное меню админа
# =========================
@router.callback_query(F.data == "admin_main", F.from_user.id.in_(ADMIN_IDS))
async def admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠 <b>Панель управления администратора</b>\nВыберите действие:",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()


# =========================
# 🔙 Возврат в главное меню
# =========================
@router.callback_query(F.data == "back_to_main")
async def back_home(callback: CallbackQuery):
    is_admin_check = callback.from_user.id in ADMIN_IDS

    await callback.message.edit_text(
        '<b>Привет! Я математический бот Math Tutor 🤖</b>\n'
            'Я могу помочь тебе разобраться в математике, сделать из эксперта '
            'по математическому анализу, дать почитать лекции и это еще не все 😉\n\n'
            'Выбери нужный раздел:',
        reply_markup=kb.get_start_kb(is_admin_check),
        parse_mode='HTML'
    )
    await callback.answer()


# =========================
# 📊 Статистика пользователей
# =========================
@router.callback_query(F.data == "admin_statistics", F.from_user.id.in_(ADMIN_IDS))
async def get_users_statistics(callback: CallbackQuery):
    total = await count_users()

    await callback.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"• Всего пользователей в базе: <code>{total}</code>",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()


# =========================
# 📚 Добавление лекций (заглушка)
# =========================
@router.callback_query(F.data == "admin_add_lecture", F.from_user.id.in_(ADMIN_IDS))
async def add_lecture_stub(callback: CallbackQuery):
    await callback.answer(
        "🚧 Функция 'Добавить лекцию' в разработке!",
        show_alert=True
    )


# =========================
# Чистая прибыль
# =========================
@router.callback_query(F.data == "admin_profit", F.from_user.id.in_(ADMIN_IDS))
async def view_profit(callback: CallbackQuery):

    users = await count_users()
    subscription_price = 300
    host_price = 500
    api_price = 1500
    profit = users * subscription_price - host_price - api_price
    expenses = host_price + api_price

    await callback.message.edit_text(
        f"💰 <b>Ваша чистая прибыль</b>\n\n"
        f"При данных параметрах:\n"
        f"• Цена подписки - 300₽\n"
        f"• Цена API - 1500₽\n"
        f"• Цена хостинга - 500₽\n\n"
        f"<b>Чистая прибыль составляет:</b> <code>{profit}₽</code>\n"
        f"<b>Расходы составляют:</b> <code>{expenses}₽</code>\n",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()




# =========================
# 📢 (Заготовка) Рассылка
# =========================
# Ниже оставлен код для будущей реализации массовой рассылки

# @router.message(Command("broadcast"), F.from_user.id.in_(ADMIN_IDS))
# async def cmd_broadcast(message: Message, bot: Bot):
#     broadcast_text = message.text.replace("/broadcast", "").strip()
#
#     if not broadcast_text:
#         await message.answer(
#             "❌ Введите текст: <code>/broadcast привет всем!</code>",
#             parse_mode='HTML'
#         )
#         return
#
#     users = await get_all_users()
#     count = 0
#
#     await message.answer(f"📢 Начинаю рассылку на {len(users)} пользователей...")
#
#     for user_id in users:
#         try:
#             await bot.send_message(user_id, broadcast_text)
#             count += 1
#             await asyncio.sleep(0.05)  # анти-флуд
#         except Exception:
#             continue
#
#     await message.answer(
#         f"✅ Рассылка завершена!\nДоставлено: <b>{count}</b>",
#         parse_mode='HTML'
#     )