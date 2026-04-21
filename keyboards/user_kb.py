"""
keyboards/user_kb.py

Изменения:
- Добавлена кнопка «💼 Кошелёк» в раздел «Личное»
- Добавлена кнопка «💳 Подписка» в профиль
- Обновлена admin_panel (тарифы, промокоды, рассылка)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# 🏠 Главное меню
# =========================
def get_start_kb(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai_tutor_menu"),
            InlineKeyboardButton(text="📚 Образование",  callback_data="education")
        ],
        [
            InlineKeyboardButton(text="🎯 Фокус",    callback_data="focus"),
            InlineKeyboardButton(text="📝 Услуги",   callback_data="services")
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
# 🔒 Меню для неоплативших (только Личное + Услуги)
# =========================
def get_locked_kb(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📝 Услуги", callback_data="services"),
            InlineKeyboardButton(text="👤 Личное", callback_data="personal")
        ],
        [
            InlineKeyboardButton(text="💳 Купить доступ", callback_data="wallet_view")
        ]
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_main")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🎓 ИИ-репетитор
# =========================
ai_tutor_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="✍️ Практика",      callback_data="practice")],
    [InlineKeyboardButton(text="💡 Дополнительные функции", callback_data="ai_additional_functions")],
    [InlineKeyboardButton(text="⬅️ Назад",          callback_data="back_to_main")]
])

ai_additional_functions = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Графический калькулятор", callback_data="graphical_calculator")],
    [InlineKeyboardButton(text="Научный калькулятор", callback_data="scientific_calculator")],
    [InlineKeyboardButton(text="Арифметический калькулятор", callback_data="arithmetic_calculator")],
    [InlineKeyboardButton(text="3D-калькулятор", callback_data="3D_calculator")],
    [InlineKeyboardButton(text="Геометрические инструменты", callback_data="geometric_tools")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_ai_tutor_menu")]
])

# =========================
# 📚 Образование
# =========================
education = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📆 Расписание", callback_data="schedule")],
    [InlineKeyboardButton(text="📖 Лекции",     callback_data="lectures")],
    [InlineKeyboardButton(text="⬅️ Назад",       callback_data="back_to_main")]
])

schedule = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="education")]
])

lectures = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📁 PDF-лекции", callback_data="pdf-lectures")],
    [InlineKeyboardButton(text="📓 Конспекты",  callback_data="notes")],
    [InlineKeyboardButton(text="⬅️ Назад",       callback_data="education")]
])


# =========================
# 🎯 Фокус
# =========================
focus = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ To-Do список дел", callback_data="to_do_list")],
    [InlineKeyboardButton(text="🍅 Таймер Помодоро", callback_data="pomodoro_timer")],
    [InlineKeyboardButton(text="🎧 Музыка", callback_data="music")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
])


# =========================
# 📝 Услуги
# =========================
services = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖨️ Распечатка",      callback_data="print")],
    [InlineKeyboardButton(text="👨‍💻 Работы на заказ", callback_data="paid_works")],
    [InlineKeyboardButton(text="⬅️ Назад",            callback_data="back_to_main")]
])

print = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Написать менеджеру", url="https://t.me/infinityriver")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_services")]
])

paid_works = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👉 Презентация", callback_data="presentation")],
    [InlineKeyboardButton(text="⬅️ Назад",       callback_data="backward_to_services")]
])

presentation = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Шаблон 1", callback_data="pr_1")],
    [InlineKeyboardButton(text="Шаблон 2", callback_data="pr_2")],
    [InlineKeyboardButton(text="Шаблон 3", callback_data="pr_3")],
    [InlineKeyboardButton(text="Шаблон 4", callback_data="pr_4")],
    [InlineKeyboardButton(text="Шаблон 5", callback_data="pr_5")],
    [InlineKeyboardButton(text="⬅️ Назад",  callback_data="backward_to_paid_works")]
])

order_pr_1 = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Заказать", url="https://t.me/mermely?text=Хочу%20заказать%20презентацию%20по%20шаблону%20%22Минимализм%22")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_presentation")]
])
order_pr_2 = order_pr_1
order_pr_3 = order_pr_1
order_pr_4 = order_pr_1
order_pr_5 = order_pr_1


# =========================
# 👤 Личное
# =========================
personal = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Профиль",     callback_data="profile")],
    [InlineKeyboardButton(text="💼 Кошелёк",    callback_data="wallet_view")],
    [InlineKeyboardButton(text="🌐 Наш сайт",   url="https://infinityriverdev.github.io/math-bot-site/")],
    [InlineKeyboardButton(text="🗣️ Отзывы", url="https://t.me/MathTutor_feedback")],
    [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/udhdhduduuwu")],
    [InlineKeyboardButton(text="⬅️ Назад",       callback_data="back_to_main")]
])


# =========================
# 👤 Профиль
# =========================
profile = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔒 Данные пользователя", callback_data="user_data")],
    [InlineKeyboardButton(text="💳 Подписка / Тарифы",   callback_data="wallet_buy_plan")],
    [InlineKeyboardButton(text="⭐ Мои XP",               callback_data="my_xp")],
    [InlineKeyboardButton(text="⬅️ Назад",                callback_data="personal")]
])


# =========================
# ⚙️ Админ-панель
# =========================
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Статистика",          callback_data="admin_statistics")],
    [InlineKeyboardButton(text="📦 Управление тарифами", callback_data="admin_plans")],
    [InlineKeyboardButton(text="🎟 Промокоды",           callback_data="admin_promos")],
    [InlineKeyboardButton(text="📝 Добавить лекцию",     callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="📢 Рассылка",            callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="🔍 Поиск по ID",         callback_data="admin_find_user")],
    [InlineKeyboardButton(text="🚫 Баны",                callback_data="admin_bans")],
    [InlineKeyboardButton(text="💰 Чистая прибыль",      callback_data="admin_profit")],
    [InlineKeyboardButton(text="⚠️ Самоликвидация!!! ⚠️", callback_data="self_destruction")],
    [InlineKeyboardButton(text="⬅️ Назад",               callback_data="back_to_main")],
    [InlineKeyboardButton(text="🤖 Групповой чат", callback_data="admin_group_chat")],
])