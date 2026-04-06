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
            InlineKeyboardButton(text="🎯 Фокус", callback_data="focus"),
            InlineKeyboardButton(text="📆 Расписание", callback_data="schedule")
        ],
        [
            InlineKeyboardButton(text="📝 Услуги", callback_data="services"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(
                text="🌐 Наш сайт",
                url="https://infinityriverdev.github.io/math-bot-site/"
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Поддержка",
                url="https://t.me/udhdhduduuwu"
            )
        ]
    ]

    # Добавляем кнопку админки, если пользователь админ
    if is_admin:
        buttons.append([
            InlineKeyboardButton(
                text="⚙️ Админ-панель",
                callback_data="admin_main",
                style='primary'
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🤖 Раздел "ИИ"
# =========================
ai = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🧮 Умнейший калькулятор", callback_data="calculator")],
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="✍️ Практика", callback_data="practice")],
    [InlineKeyboardButton(text="🔄 Выбрать ИИ", callback_data="choose_ai")],
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
#  Раздел "Фокус"
# =========================
focus = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎧 Музыка", callback_data="music")],
    [InlineKeyboardButton(text="🍅 Таймер Помодоро", callback_data="pomodoro_timer")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
#  Раздел "Фокус"
# =========================
schedule = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Посмотреть расписание", callback_data="view_schedule")],
    [InlineKeyboardButton(text="✅ To-Do список дел", callback_data="to_do_list")],
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

print = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Написать менеджеру", url="https://t.me/infinityriver")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_services")]
])


# =========================
# 👤 Раздел "Профиль"
# =========================
profile = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔒 Данные пользователя", callback_data="user_data")],
    [InlineKeyboardButton(text="🟢 Подписка", callback_data="paid_works")],
    [InlineKeyboardButton(text="⭐ Мои XP", callback_data="my_xp")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# ⚙️ Админ-панель
# =========================
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Статистика пользователей", callback_data="admin_statistics")],
    [InlineKeyboardButton(text="📝 Добавить лекцию", callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="💰 Чистая прибыль", callback_data="admin_profit")],
    [InlineKeyboardButton(text="⚠️Самоликвидация!!!⚠️", callback_data="self_destruction", style='danger')],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])