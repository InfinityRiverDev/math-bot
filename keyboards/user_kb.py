from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Главная клавиатура
def get_start_kb(is_admin: bool):
    buttons = [
        [InlineKeyboardButton(text="🧮 Умнейший калькулятор", callback_data="calculator")],
        [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
        [InlineKeyboardButton(text="📚 Лекции", callback_data="lectures")]
    ]

    # ПРОВЕРЬТЕ ЗДЕСЬ: Должен быть InlineKeyboardButton, а не KeyboardButton
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Админ-панель
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Количество пользователей", callback_data="admin_count")],
    [InlineKeyboardButton(text="📝 Добавить лекцию", callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])