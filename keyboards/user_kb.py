from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


### Главная клавиатура
def get_start_kb(is_admin: bool):
    buttons = [
        [InlineKeyboardButton(text="🧠 ИИ", callback_data="ai"), InlineKeyboardButton(text="📚 Лекции", callback_data="lectures")],
        [InlineKeyboardButton(text="📝 Услуги", callback_data="services"), InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support", url="https://t.me/damn_the_bucks")]
    ]

    # ПРОВЕРЬТЕ ЗДЕСЬ: Должен быть InlineKeyboardButton, а не KeyboardButton
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


### ИИ
ai = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧮 Умнейший калькулятор", callback_data="calculator")],
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="🔄 Выбрать ИИ", callback_data="choose_ai")],
    [InlineKeyboardButton(text="✍️ Практика", callback_data="practice")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


### Лекции
lectures = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📁 PDF-лекции", callback_data="pdf-lectures")],
    [InlineKeyboardButton(text="📓 Конспекты", callback_data="notes")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


### Услуги
services = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖨️ Распечатка", callback_data="print")],
    [InlineKeyboardButton(text="👨‍💻 Работы на заказ", callback_data="paid_works")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


### Профиль
profile = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔒 Данные пользователя", callback_data="print")],
    [InlineKeyboardButton(text="🟢 Подписка", callback_data="paid_works")],
    [InlineKeyboardButton(text="⭐ Мои XP", callback_data="my_xp")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


### Админ-панель
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Количество пользователей", callback_data="admin_count")],
    [InlineKeyboardButton(text="📝 Добавить лекцию", callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])

