from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# 🏠 Главное меню
# =========================
def get_start_kb(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai_tutor_menu"),
            InlineKeyboardButton(text="📚 Образование", callback_data="education")
        ],
        [
            InlineKeyboardButton(text="🎯 Фокус", callback_data="focus"),
            InlineKeyboardButton(text="📝 Услуги", callback_data="services")
        ],
        [
            InlineKeyboardButton(text="👤 Личное", callback_data="personal")
        ]
    ]

    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_main")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🎓 ИИ-репетитор (бывший раздел ИИ — объединён)
# =========================
ai_tutor_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="✍️ Практика", callback_data="practice")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📚 Образование (Расписание + Лекции)
# =========================
education = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📆 Расписание", callback_data="schedule")],
    [InlineKeyboardButton(text="📖 Лекции", callback_data="lectures")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📆 Расписание
# =========================
schedule = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Посмотреть расписание", callback_data="view_schedule")],
    [InlineKeyboardButton(text="✅ To-Do список дел", callback_data="to_do_list")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="education")]
])


# =========================
# 📖 Лекции
# =========================
lectures = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📁 PDF-лекции", callback_data="pdf-lectures")],
    [InlineKeyboardButton(text="📓 Конспекты", callback_data="notes")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="education")]
])


# =========================
# 🎯 Фокус
# =========================
focus = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎧 Музыка", callback_data="music")],
    [InlineKeyboardButton(text="🍅 Таймер Помодоро", callback_data="pomodoro_timer")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📝 Услуги
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
# 👤 Личное (Профиль + Поддержка + Сайт)
# =========================
personal = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
    [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/udhdhduduuwu")],
    [InlineKeyboardButton(
        text="🌐 Наш сайт",
        url="https://infinityriverdev.github.io/math-bot-site/"
    )],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 👤 Профиль (внутри раздела Личное)
# =========================
profile = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔒 Данные пользователя", callback_data="user_data")],
    [InlineKeyboardButton(text="🟢 Подписка", callback_data="paid_works")],
    [InlineKeyboardButton(text="⭐ Мои XP", callback_data="my_xp")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="personal")]
])


# =========================
# ⚙️ Админ-панель
# =========================
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Статистика пользователей", callback_data="admin_statistics")],
    [InlineKeyboardButton(text="📝 Добавить лекцию", callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="💰 Чистая прибыль", callback_data="admin_profit")],
    [InlineKeyboardButton(text="⚠️ Самоликвидация!!! ⚠️", callback_data="self_destruction")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])