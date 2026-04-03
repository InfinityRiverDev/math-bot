import asyncio
import os
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database.models import count_users, get_all_users
from dotenv import load_dotenv
import keyboards.user_kb as kb


load_dotenv()

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_ID"))


# Фильтр для проверки, является ли пользователь админом
def is_admin(message: Message):
    return message.from_user.id == ADMIN_ID


# Вход в админку по нажатию инлайн-кнопки
@router.callback_query(F.data == "admin_main", F.from_user.id == ADMIN_ID)
async def admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠 <b>Панель управления администратора</b>\nВыберите действие:",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()

# Кнопка "Назад" (возвращает в главное меню)
@router.callback_query(F.data == "back_to_main")
async def back_home(callback: CallbackQuery):
    # Проверяем, админ ли тот, кто нажал "Назад"
    is_admin_check = callback.from_user.id == ADMIN_ID

    await callback.message.edit_text(
        "Привет! Я математический бот 🤖\nВыбери что хочешь сделать:",
        reply_markup=kb.get_start_kb(is_admin_check),
        parse_mode='HTML'
    )
    await callback.answer()

# @router.message(Command("admin"), F.from_user.id == ADMIN_ID)
# async def cmd_admin_stats(message: Message):
#     total = await count_users()
#     await message.answer(
#         f"<b>📊 Статистика бота</b>\n\n"
#         f"• Всего пользователей в базе: <code>{total}</code>",
#         parse_mode='HTML'
#     )
#
#
# @router.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
# async def cmd_broadcast(message: Message, bot: Bot):
#     # Текст после команды: /broadcast Привет!
#     broadcast_text = message.text.replace("/broadcast", "").strip()
#
#     if not broadcast_text:
#         await message.answer("❌ Введите текст: <code>/broadcast привет всем!</code>", parse_mode='HTML')
#         return
#
#     users = await get_all_users()
#     count = 0
#     await message.answer(f"📢 Начинаю рассылку на {len(users)} пользователей...")
#
#     for user_id in users:
#         try:
#             await bot.send_message(user_id, broadcast_text)
#             count += 1
#             await asyncio.sleep(0.05)  # Защита от флуд-контроля Telegram
#         except Exception:
#             continue
#
#     await message.answer(f"✅ Рассылка завершена!\nДоставлено: <b>{count}</b>", parse_mode='HTML')


# Обработка кнопки "Количество пользователей"
@router.callback_query(F.data == "admin_count", F.from_user.id == ADMIN_ID)
async def get_users_count(callback: CallbackQuery):
    total = await count_users()
    # edit_text обновляет сообщение, показывая цифру
    await callback.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"• Всего пользователей в базе: <code>{total}</code>",
        reply_markup=kb.admin_panel, # Возвращаем кнопки, чтобы можно было вернуться или нажать другое
        parse_mode='HTML'
    )
    await callback.answer() # Убирает индикатор загрузки на кнопке

# Заглушка для кнопки "Добавить лекцию"
@router.callback_query(F.data == "admin_add_lecture", F.from_user.id == ADMIN_ID)
async def add_lecture_stub(callback: CallbackQuery):
    # show_alert=True покажет уведомление прямо по центру экрана
    await callback.answer("🚧 Функция 'Добавить лекцию' в разработке!", show_alert=True)