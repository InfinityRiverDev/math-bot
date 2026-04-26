"""
keyboards/user_kb.py
"""

import os
import urllib.parse
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# WEBAPP_URL задаётся один раз здесь
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://math-tutor-webapp.vercel.app/")


def _wa(path: str) -> WebAppInfo:
    """Хелпер: создаёт WebAppInfo с нужным путём."""
    url = WEBAPP_URL.rstrip("/") + path
    return WebAppInfo(url=url)


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
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🔒 Меню для неоплативших
# =========================
def get_locked_kb(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📝 Услуги", callback_data="services"),
            InlineKeyboardButton(text="👤 Личное", callback_data="personal")
        ],
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="wallet_view")]
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🎓 ИИ-репетитор
# =========================
ai_tutor_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎓 ИИ-репетитор", callback_data="ai-tutor")],
    [InlineKeyboardButton(text="✍️ Практика",      callback_data="practice")],
    [InlineKeyboardButton(text="🎨 Генерация картинок", callback_data="ai_art")],
    [InlineKeyboardButton(text="⬅️ Назад",          callback_data="back_to_main")]
])


# =========================
# 📚 Образование
# =========================
education = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📆 Расписание", callback_data="schedule")],
    [InlineKeyboardButton(text="📖 Лекции",     callback_data="lectures")],
    [InlineKeyboardButton(text="📈 Графический калькулятор", web_app=_wa("/?desmos=graphing"))],
    [InlineKeyboardButton(text="🔬 Научный калькулятор", web_app=_wa("/?desmos=scientific"))],
    [InlineKeyboardButton(text="🌐 3D-калькулятор", web_app=_wa("/?desmos=3d"))],
    [InlineKeyboardButton(text="📐 Геометрия", web_app=_wa("/?desmos=geometry"))],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
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

print_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Написать менеджеру", url="https://t.me/infinityriver")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_services")]
])

paid_works = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👉 Презентация", callback_data="presentation")],
    [InlineKeyboardButton(text="⬅️ Назад",       callback_data="backward_to_services")]
])

# =============================================================
# 🖼 КНОПКИ ВЫБОРА ШАБЛОНОВ ПРЕЗЕНТАЦИЙ
# =============================================================
# Меняй только text= — это название, которое видит пользователь.
# callback_data= НЕ ТРОГАЙ — он связан с обработчиком в user.py.
#
# ⚠️ Важно: значение text= здесь должно СОВПАДАТЬ с "name"
#    соответствующего шаблона в словаре TEMPLATES в user.py,
#    потому что именно оно передаётся в ссылку заказа.
# =============================================================
presentation = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🖼 Шаблон 1 — [название]", callback_data="collage_1")],  # ← МЕНЯЙ text=
    [InlineKeyboardButton(text="🖼 Шаблон 2 — [название]", callback_data="collage_2")],  # ← МЕНЯЙ text=
    [InlineKeyboardButton(text="🖼 Шаблон 3 — [название]", callback_data="collage_3")],  # ← МЕНЯЙ text=
    [InlineKeyboardButton(text="🖼 Шаблон 4 — [название]", callback_data="collage_4")],  # ← МЕНЯЙ text=
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_paid_works")]
])


# =========================
# 👤 Личное
# =========================
personal = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Профиль",     callback_data="profile")],
    [InlineKeyboardButton(text="💼 Кошелёк",    callback_data="wallet_view")],
    [InlineKeyboardButton(text="🌐 Наш сайт",   url="https://infinityriverdev.github.io/math-bot-site/")],
    [InlineKeyboardButton(text="🗣️ Отзывы", url="https://t.me/KNRTU_core_feedback")],
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

admin_panel_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Статистика",          callback_data="admin_statistics")],
    [InlineKeyboardButton(text="💰 Финансы",             callback_data="admin_profit")],
    [InlineKeyboardButton(text="📦 Тарифы и промокоды",  callback_data="admin_plans_promos")],
    [InlineKeyboardButton(text="📖 Лекции",              callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="📢 Рассылка",            callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="👤 Пользователи",        callback_data="admin_users_menu")],
    [InlineKeyboardButton(text="💬 Групповой чат",       callback_data="admin_group_chat")],
    [InlineKeyboardButton(text="⚠️ Самоликвидация",      callback_data="self_destruction")],
    [InlineKeyboardButton(text="⬅️ Назад",               callback_data="back_to_main")]
])

admin_plans_promos = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📦 Управление тарифами", callback_data="admin_plans")],
    [InlineKeyboardButton(text="🎟 Промокоды",           callback_data="admin_promos")],
    [InlineKeyboardButton(text="⬅️ Назад",               callback_data="admin_panel_main")]
])

admin_users_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔍 Поиск по ID",    callback_data="admin_find_user")],
    [InlineKeyboardButton(text="🚫 Баны",           callback_data="admin_bans")],
    [InlineKeyboardButton(text="⬅️ Назад",          callback_data="admin_panel_main")]
])

# Для обратной совместимости
admin_panel = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Статистика",          callback_data="admin_statistics")],
    [InlineKeyboardButton(text="📦 Тарифы и промокоды",  callback_data="admin_plans_promos")],
    [InlineKeyboardButton(text="📖 Лекции",              callback_data="admin_add_lecture")],
    [InlineKeyboardButton(text="📢 Рассылка",            callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="👤 Пользователи",        callback_data="admin_users_menu")],
    [InlineKeyboardButton(text="💬 Групповой чат",       callback_data="admin_group_chat")],
    [InlineKeyboardButton(text="💰 Финансы",             callback_data="admin_profit")],
    [InlineKeyboardButton(text="⚠️ Самоликвидация",      callback_data="self_destruction")],
    [InlineKeyboardButton(text="⬅️ Назад",               callback_data="back_to_main")]
])


# =========================
# 🤖 Групповой чат (админ)
# =========================
def get_group_chat_kb(groups: list) -> InlineKeyboardMarkup:
    """Список групп с кнопками управления."""
    buttons = []
    for g in groups:
        status = "✅" if g.get("enabled") else "❌"
        title = g.get("chat_title") or str(g["chat_id"])
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {title}",
                callback_data=f"gc_toggle_{g['chat_id']}"
            )
        ])
        laziness = g.get("laziness", 60)
        buttons.append([
            InlineKeyboardButton(text=f"🦥 Лень: {laziness}%", callback_data=f"gc_lazy_{g['chat_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_laziness_kb(chat_id: int, current: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора значения лени."""
    levels = [0, 20, 40, 60, 80, 95]
    buttons = []
    row = []
    for val in levels:
        mark = "✅ " if val == current else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{val}%",
            callback_data=f"gc_setlazy_{chat_id}_{val}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_group_chat")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_order_pr_kb(template_name: str) -> InlineKeyboardMarkup:
    """Кнопка заказа — открывает миниапп сразу в чат презентаций."""
    encoded = urllib.parse.quote(template_name)
    url = f"{WEBAPP_URL.rstrip('/')}/?page=services&openchat=presentation&template={encoded}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Заказать в чате", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="backward_to_presentation")]
    ])