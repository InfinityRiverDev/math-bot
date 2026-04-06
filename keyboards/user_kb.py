from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# 🏠 Главное меню
# =========================
def get_start_kb(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🧠 ИИ", callback_data="ai"),
            InlineKeyboardButton(text="📚 Лекции", callback_data="lectures")
        ],
        [
            InlineKeyboardButton(text="📝 Услуги", callback_data="services"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(
                text="💬 Поддержка",
                url="https://t.me/damn_the_bucks"
            )
        ]
    ]

    # Добавляем кнопку админки, если пользователь админ
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_main")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🤖 Раздел "ИИ"
# =========================
ai = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧮 Умнейший калькулятор", callback_data="calculator")],
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="🔄 Выбрать ИИ", callback_data="choose_ai")],
    [InlineKeyboardButton(text="✍️ Практика", callback_data="practice")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📚 Раздел "Лекции"
# =========================
lectures = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📁 PDF-лекции", callback_data="pdf-lectures")],
    [InlineKeyboardButton(text="📓 Конспекты", callback_data="notes")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📝 Раздел "Услуги"
# =========================
services = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖨️ Распечатка", callback_data="print")],
    [InlineKeyboardButton(text="👨‍💻 Работы на заказ", callback_data="paid_works")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 👤 Раздел "Профиль"
# =========================
profile = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔒 Данные пользователя", callback_data="print")],
    [InlineKeyboardButton(text="🟢 Подписка", callback_data="paid_works")],
    [InlineKeyboardButton(text="⭐ Мои XP", callback_data="my_xp")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# ⚙️ Админ-панель
# =========================
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Количество пользователей", callback_data="admin_count")],
    [InlineKeyboardButton(text="📝 Добавить лекцию", callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])