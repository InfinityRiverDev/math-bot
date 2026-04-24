"""
handlers/admin.py

Изменения:
- Рассылка: две кнопки «Всем» и «По ID»
- «По ID» принимает один или несколько ID через запятую/пробел
"""

import asyncio
import os
import re

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from database.models import count_users, get_all_users
from database.billing_models import (
    get_all_plans, get_plan, create_plan, update_plan, delete_plan,
    get_all_promo_codes, create_promo, delete_promo,
    has_active_subscription
)
import keyboards.user_kb as kb

load_dotenv()

router = Router()
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS").split(",")))


# ===========================
# FSM
# ===========================

class AdminStates(StatesGroup):
    # Тарифы
    plan_name         = State()
    plan_price        = State()
    plan_duration     = State()
    plan_description  = State()
    edit_plan_field   = State()
    edit_plan_value   = State()
    # Промокоды
    promo_code        = State()
    promo_discount    = State()
    promo_max_uses    = State()
    # Рассылка
    broadcast_text_all   = State()   # текст для рассылки всем
    broadcast_ids        = State()   # ввод ID получателей
    broadcast_text_ids   = State()   # текст для рассылки по ID
    # Баны
    ban_ids = State()
    ban_confirm = State()
    unban_ids = State()
    unban_confirm = State()
    ban_duration = State()
    ban_reason = State()
    # Поиск юзера
    find_user_ids = State()


def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


# ===========================
# Главное меню
# ===========================

@router.callback_query(F.data == "admin_panel_main", F.from_user.id.in_(ADMIN_IDS))
async def admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠 <b>Панель управления администратора</b>\nВыберите раздел:",
        reply_markup=kb.admin_panel_main,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_home(callback: CallbackQuery):
    is_admin_check = callback.from_user.id in ADMIN_IDS
    has_sub = await has_active_subscription(callback.from_user.id)

    reply_markup = (
        kb.get_start_kb(is_admin_check)
        if is_admin_check or has_sub
        else kb.get_locked_kb(is_admin_check)
    )

    await callback.message.edit_text(
        '👋 <b>Добро пожаловать в Math Tutor!</b>\n\n'
                    '🤖 Я помогу тебе с математикой, прослежу за твоим расписанием '
                    'и автоматически отмечу тебя на парах.\n\n'
                    '👇 Выбери раздел:',
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    await callback.answer()


# ===========================
# Статистика
# ===========================

# @router.callback_query(F.data == "admin_statistics", F.from_user.id.in_(ADMIN_IDS))
# async def get_users_statistics(callback: CallbackQuery):
#     total = await count_users()
#     await callback.message.edit_text(
#         f"📊 <b>Статистика бота</b>\n\n"
#         f"• Всего пользователей в базе: <code>{total}</code>",
#         reply_markup=kb.admin_panel,
#         parse_mode='HTML'
#     )
#     await callback.answer()


# ===========================
# Чистая прибыль
# ===========================

@router.callback_query(F.data == "admin_profit", F.from_user.id.in_(ADMIN_IDS))
async def view_profit(callback: CallbackQuery):
    users_count = await count_users()
    subscription_price = 300
    host_price = 500
    api_price = 1500
    profit = users_count * subscription_price - host_price - api_price
    expenses = host_price + api_price
    await callback.message.edit_text(
        f"💰 <b>Чистая прибыль</b>\n\n"
        f"• Цена подписки: 300₽\n"
        f"• API: {api_price}₽\n"
        f"• Хостинг: {host_price}₽\n\n"
        f"<b>Прибыль:</b> <code>{profit}₽</code>\n"
        f"<b>Расходы:</b> <code>{expenses}₽</code>",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()


# ===========================
# Тарифы — список
# ===========================

async def plans_admin_kb() -> InlineKeyboardMarkup:
    all_plans = await get_all_plans()
    buttons = []
    for p in all_plans:
        buttons.append([
            InlineKeyboardButton(
                text=f"📦 {p['name']} — {p['price']}₽",
                callback_data=f"admin_plan_view_{p['_id']}"
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_plan_del_{p['_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Создать тариф", callback_data="admin_plan_create")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_plans", F.from_user.id.in_(ADMIN_IDS))
async def admin_plans_list(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📦 <b>Управление тарифами</b>",
        reply_markup=await plans_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Тариф — просмотр/редактирование
# ===========================

def plan_edit_kb(plan_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название",    callback_data=f"admin_plan_edit_{plan_id}_name")],
        [InlineKeyboardButton(text="✏️ Цена",        callback_data=f"admin_plan_edit_{plan_id}_price")],
        [InlineKeyboardButton(text="✏️ Срок",        callback_data=f"admin_plan_edit_{plan_id}_duration_days")],
        [InlineKeyboardButton(text="✏️ Описание",    callback_data=f"admin_plan_edit_{plan_id}_description")],
        [InlineKeyboardButton(text="🗑 Удалить",     callback_data=f"admin_plan_del_{plan_id}")],
        [InlineKeyboardButton(text="⬅️ Назад",       callback_data="admin_plans")],
    ])


@router.callback_query(F.data.startswith("admin_plan_view_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_view(callback: CallbackQuery):
    await callback.answer()
    plan_id = callback.data.replace("admin_plan_view_", "")
    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    text = (
        f"📦 <b>{plan['name']}</b>\n\n"
        f"💰 Цена: {plan['price']}₽\n"
        f"📅 Срок: {plan['duration_days']} дней\n"
        f"📝 Описание: {plan.get('description') or '—'}"
    )
    await callback.message.edit_text(text, reply_markup=plan_edit_kb(plan_id), parse_mode='HTML')


# ===========================
# Создание тарифа
# ===========================

@router.callback_query(F.data == "admin_plan_create", F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_create_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.plan_name)
    await callback.message.edit_text(
        "📦 <b>Новый тариф</b>\n\nВведите <b>название</b>:",
        parse_mode='HTML'
    )


@router.message(AdminStates.plan_name, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_name(message: Message, state: FSMContext):
    await state.update_data(plan_name=message.text.strip())
    await state.set_state(AdminStates.plan_price)
    await message.answer("💰 Введите <b>цену</b> в рублях:", parse_mode='HTML')


@router.message(AdminStates.plan_price, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    await state.update_data(plan_price=price)
    await state.set_state(AdminStates.plan_duration)
    await message.answer("📅 Введите <b>срок действия</b> в днях:", parse_mode='HTML')


@router.message(AdminStates.plan_duration, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_duration(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число.")
        return
    await state.update_data(plan_duration=days)
    await state.set_state(AdminStates.plan_description)
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="admin_plan_skip_desc")]
    ])
    await message.answer("📝 Введите <b>описание</b> (или пропустите):", reply_markup=skip_kb, parse_mode='HTML')


@router.callback_query(F.data == "admin_plan_skip_desc", F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_skip_desc(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(plan_description="")
    await _finish_create_plan(callback.message, state)


@router.message(AdminStates.plan_description, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_description(message: Message, state: FSMContext):
    await state.update_data(plan_description=message.text.strip())
    await _finish_create_plan(message, state)


async def _finish_create_plan(message, state: FSMContext):
    data = await state.get_data()
    await create_plan(
        name=data["plan_name"],
        price=data["plan_price"],
        duration_days=data["plan_duration"],
        description=data.get("plan_description", "")
    )
    await state.clear()
    await message.answer(
        f"✅ Тариф <b>{data['plan_name']}</b> создан!\n"
        f"💰 {data['plan_price']}₽ / {data['plan_duration']} дней",
        reply_markup=await plans_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Редактирование поля тарифа
# ===========================

PLAN_FIELD_LABELS = {
    "name": "название",
    "price": "цену (число)",
    "duration_days": "срок в днях (число)",
    "description": "описание"
}


@router.callback_query(F.data.startswith("admin_plan_edit_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_edit_field(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.replace("admin_plan_edit_", "").rsplit("_", 1)
    if len(parts) != 2:
        return
    plan_id, field = parts[0], parts[1]
    await state.update_data(edit_plan_id=plan_id, edit_plan_field=field)
    await state.set_state(AdminStates.edit_plan_value)
    label = PLAN_FIELD_LABELS.get(field, field)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_plan_view_{plan_id}")]
    ])
    await callback.message.edit_text(
        f"✏️ Введите новое <b>{label}</b>:",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(AdminStates.edit_plan_value, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    plan_id = data["edit_plan_id"]
    field   = data["edit_plan_field"]
    raw     = message.text.strip()

    if field == "price":
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число.")
            return
    elif field == "duration_days":
        try:
            value = int(raw)
        except ValueError:
            await message.answer("❌ Введите целое число.")
            return
    else:
        value = raw

    await update_plan(plan_id, **{field: value})
    await state.clear()
    await message.answer("✅ Поле обновлено.", reply_markup=await plans_admin_kb(), parse_mode='HTML')


# ===========================
# Удаление тарифа
# ===========================

@router.callback_query(F.data.startswith("admin_plan_del_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_delete(callback: CallbackQuery):
    plan_id = callback.data.replace("admin_plan_del_", "")
    await delete_plan(plan_id)
    await callback.answer("🗑 Тариф удалён")
    await callback.message.edit_text(
        "📦 <b>Управление тарифами</b>",
        reply_markup=await plans_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Промокоды — список
# ===========================

async def promos_admin_kb() -> InlineKeyboardMarkup:
    codes = await get_all_promo_codes()
    buttons = []
    for p in codes:
        label = f"🎟 {p['code']} — {p['discount_percent']}%"
        if p.get("max_uses"):
            label += f" ({p['uses_count']}/{p['max_uses']})"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data="noop"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_promo_del_{p['_id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_promos", F.from_user.id.in_(ADMIN_IDS))
async def admin_promos_list(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🎟 <b>Промокоды</b>", reply_markup=await promos_admin_kb(), parse_mode='HTML')


@router.callback_query(F.data == "admin_promo_create", F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_create_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.promo_code)
    await callback.message.edit_text(
        "🎟 <b>Новый промокод</b>\n\nВведите <b>код</b> (например: <code>SAVE20</code>):",
        parse_mode='HTML'
    )


@router.message(AdminStates.promo_code, F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if len(code) < 3:
        await message.answer("❌ Слишком короткий код.")
        return
    await state.update_data(new_promo_code=code)
    await state.set_state(AdminStates.promo_discount)
    await message.answer("💸 Введите <b>скидку в %</b> (1–99):", parse_mode='HTML')


@router.message(AdminStates.promo_discount, F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_discount(message: Message, state: FSMContext):
    try:
        discount = int(message.text.strip())
        if not 1 <= discount <= 99:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 99.")
        return
    await state.update_data(new_promo_discount=discount)
    await state.set_state(AdminStates.promo_max_uses)
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ Без ограничений", callback_data="admin_promo_unlimited")]
    ])
    await message.answer("🔢 Введите <b>макс. кол-во использований</b>:", reply_markup=skip_kb, parse_mode='HTML')


@router.callback_query(F.data == "admin_promo_unlimited", F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_unlimited(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(new_promo_max_uses=0)
    await _finish_create_promo(callback.message, state)


@router.message(AdminStates.promo_max_uses, F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число.")
        return
    await state.update_data(new_promo_max_uses=max_uses)
    await _finish_create_promo(message, state)


async def _finish_create_promo(message, state: FSMContext):
    data = await state.get_data()
    code = data["new_promo_code"]
    discount = data["new_promo_discount"]
    max_uses = data.get("new_promo_max_uses", 0)
    await create_promo(code, discount, max_uses)
    await state.clear()
    uses_text = f"Макс. использований: {max_uses}" if max_uses else "Без ограничений"
    await message.answer(
        f"✅ Промокод <b>{code}</b> создан!\nСкидка: <b>{discount}%</b>\n{uses_text}",
        reply_markup=await promos_admin_kb(),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("admin_promo_del_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_delete(callback: CallbackQuery):
    promo_id = callback.data.replace("admin_promo_del_", "")
    await delete_promo(promo_id)
    await callback.answer("🗑 Промокод удалён")
    await callback.message.edit_text("🎟 <b>Промокоды</b>", reply_markup=await promos_admin_kb(), parse_mode='HTML')


# ===========================
# 🚫 БАНЫ
# ===========================

# ===========================
# 🚫 БАНЫ
# ===========================

import re
from database.models import ban_user, unban_user

# ───────────────
# МЕНЮ БАНОВ
# ───────────────

@router.callback_query(F.data == "admin_bans", F.from_user.id.in_(ADMIN_IDS))
async def admin_bans_menu(callback: CallbackQuery):
    kb_bans = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Забанить", callback_data="admin_ban_start")],
        [InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban_start")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")]
    ])
    await callback.message.edit_text(
        "🚫 <b>Баны пользователей</b>",
        reply_markup=kb_bans,
        parse_mode='HTML'
    )
    await callback.answer()


# ───────────────
# БАН — ввод ID
# ───────────────

@router.callback_query(F.data == "admin_ban_start", F.from_user.id.in_(ADMIN_IDS))
async def ban_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.ban_ids)
    await callback.message.edit_text(
        "Введи ID (можно несколько):\n\n"
        "<i>Пример: 123456789, 987654321</i>",
        parse_mode='HTML'
    )


# ───────────────
# ПОЛУЧИЛИ ID
# ───────────────

@router.message(AdminStates.ban_ids, F.from_user.id.in_(ADMIN_IDS))
async def ban_ids(message: Message, state: FSMContext):
    ids = list(set(int(x) for x in re.findall(r'\d+', message.text)))

    if not ids:
        await message.answer("❌ Введи корректные ID")
        return

    await state.update_data(ids=ids)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ Навсегда", callback_data="ban_forever")],
        [InlineKeyboardButton(text="⏳ Временный бан", callback_data="ban_temp")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_bans")]
    ])

    await message.answer(f"Выбери тип бана для:\n<code>{ids}</code>", reply_markup=kb, parse_mode='HTML')


# ───────────────
# БАН НАВСЕГДА
# ───────────────

@router.callback_query(F.data == "ban_forever", F.from_user.id.in_(ADMIN_IDS))
async def ban_forever(callback: CallbackQuery, state: FSMContext):
    await state.update_data(duration_hours=None)
    await state.set_state(AdminStates.ban_reason)

    await callback.message.edit_text("📝 Введи причину бана:")


# ───────────────
# ВРЕМЕННЫЙ БАН
# ───────────────

@router.callback_query(F.data == "ban_temp", F.from_user.id.in_(ADMIN_IDS))
async def ban_temp(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.ban_duration)

    await callback.message.edit_text(
        "⏱ Введи длительность:\n\n"
        "• В часах: <code>12</code>\n"
        "• В днях: <code>2d</code>\n\n"
        "<i>Примеры: 24, 48, 7d</i>",
        parse_mode='HTML'
    )


# ───────────────
# ПАРСИНГ ВРЕМЕНИ
# ───────────────

@router.message(AdminStates.ban_duration, F.from_user.id.in_(ADMIN_IDS))
async def ban_duration(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    try:
        if text.endswith("d"):
            days = int(text[:-1])
            hours = days * 24
        else:
            hours = int(text)
    except:
        await message.answer("❌ Неверный формат")
        return

    await state.update_data(duration_hours=hours)
    await state.set_state(AdminStates.ban_reason)

    await message.answer("📝 Введи причину бана:")


# ───────────────
# ПРИЧИНА
# ───────────────

@router.message(AdminStates.ban_reason, F.from_user.id.in_(ADMIN_IDS))
async def ban_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)

    data = await state.get_data()

    kb_confirm = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="ban_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_bans")]
    ])

    await message.answer(
        f"🚫 <b>Подтверждение бана</b>\n\n"
        f"👤 ID: <code>{data.get('ids')}</code>\n"
        f"⏱ Срок: {'навсегда' if not data.get('duration_hours') else str(data.get('duration_hours')) + ' часов'}\n"
        f"📝 Причина: {data.get('reason')}",
        reply_markup=kb_confirm,
        parse_mode='HTML'
    )


# ───────────────
# ПРИМЕНЕНИЕ БАНА
# ───────────────

@router.callback_query(F.data == "ban_confirm", F.from_user.id.in_(ADMIN_IDS))
async def ban_apply(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    ids = data.get("ids", [])
    hours = data.get("duration_hours")
    reason = data.get("reason")

    for uid in ids:
        await ban_user(uid, hours, reason)

        # уведомление пользователю
        try:
            text = "🚫 <b>Вы заблокированы</b>"

            if hours:
                text += f"\n⏱ Срок: {hours} часов"
            else:
                text += "\n♾ Навсегда"

            if reason:
                text += f"\n📝 Причина: {reason}"

            await bot.send_message(uid, text, parse_mode='HTML')
        except:
            pass

    await state.clear()
    await callback.message.edit_text(
        "✅ Пользователи успешно забанены",
        reply_markup=kb.admin_panel
    )


# ───────────────
# РАЗБАН
# ───────────────

@router.callback_query(F.data == "admin_unban_start", F.from_user.id.in_(ADMIN_IDS))
async def unban_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.unban_ids)
    await callback.message.edit_text("Введи ID для разбана:")


@router.message(AdminStates.unban_ids, F.from_user.id.in_(ADMIN_IDS))
async def unban_users(message: Message, state: FSMContext, bot: Bot):
    ids = list(set(int(x) for x in re.findall(r'\d+', message.text)))

    if not ids:
        await message.answer("❌ Введи ID")
        return

    for uid in ids:
        await unban_user(uid)

        try:
            await bot.send_message(uid, "✅ <b>Вы были разблокированы</b>", parse_mode='HTML')
        except:
            pass

    await state.clear()
    await message.answer(
        "✅ Пользователи разбанены",
        reply_markup=kb.admin_panel
    )


# ===========================
# ✅ РАЗБАН
# ===========================

@router.callback_query(F.data == "admin_unban_start", F.from_user.id.in_(ADMIN_IDS))
async def unban_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.unban_ids)
    await callback.message.edit_text("Введи ID для разбана:")


from database.models import unban_user

@router.message(AdminStates.unban_ids, F.from_user.id.in_(ADMIN_IDS))
async def unban_users(message: Message, state: FSMContext, bot: Bot):
    import re

    ids = list(set(int(x) for x in re.findall(r'\d+', message.text)))

    for uid in ids:
        await unban_user(uid)

        # 🔥 уведомление
        try:
            await bot.send_message(uid, "✅ <b>Вы были разблокированы</b>", parse_mode='HTML')
        except:
            pass

    await state.clear()
    await message.answer("✅ Пользователи разбанены", reply_markup=kb.admin_panel)


# ===========================
# Поиск пользователя
# =========================

@router.callback_query(F.data == "admin_find_user", F.from_user.id.in_(ADMIN_IDS))
async def find_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.find_user_ids)
    await callback.message.edit_text("Введи ID пользователя:")


from database.models import get_user_full

@router.message(AdminStates.find_user_ids, F.from_user.id.in_(ADMIN_IDS))
async def find_user(message: Message, state: FSMContext):
    import re
    ids = list(set(int(x) for x in re.findall(r'\d+', message.text)))

    result = ""

    for uid in ids:
        user = await get_user_full(uid)
        if not user:
            result += f"\n❌ {uid} — не найден\n"
            continue

        result += (
            f"\n👤 <b>{user.get('first_name')} {user.get('last_name')}</b>\n"
            f"🆔 {uid}\n"
            f"📛 @{user.get('username')}\n"
            f"🏛 {user.get('institute')}\n"
            f"📚 {user.get('group_number')}\n"
        )

    await state.clear()
    await message.answer(result, parse_mode='HTML')


# ===========================
# 📢 Рассылка — выбор режима
# ===========================

def broadcast_mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Всем",   callback_data="broadcast_all"),
            InlineKeyboardButton(text="🎯 По ID",  callback_data="broadcast_by_id"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel_main")],
    ])


@router.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВыбери режим отправки:",
        reply_markup=broadcast_mode_kb(),
        parse_mode='HTML'
    )


# ===========================
# 📢 Рассылка — Всем
# ===========================

@router.callback_query(F.data == "broadcast_all", F.from_user.id.in_(ADMIN_IDS))
async def broadcast_all_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.broadcast_text_all)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")]
    ])
    total = await count_users()
    await callback.message.edit_text(
        f"👥 <b>Рассылка всем</b> ({total} пользователей)\n\n"
        "Введи текст сообщения.\n"
        "<i>Поддерживается HTML: <b>жирный</b>, <i>курсив</i>, <code>код</code></i>",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(AdminStates.broadcast_text_all, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_all_send(message: Message, state: FSMContext, bot: Bot):
    text = message.html_text or message.text or ""
    if not text.strip():
        await message.answer("❌ Пустое сообщение.")
        return

    await state.clear()
    user_ids = await get_all_users()
    total = len(user_ids)
    status_msg = await message.answer(f"📤 Начинаю рассылку на <b>{total}</b> пользователей...", parse_mode='HTML')

    sent, failed = 0, 0
    for i, uid in enumerate(user_ids, 1):
        try:
            await bot.send_message(uid, text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        if i % 30 == 0:
            await asyncio.sleep(1)

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"• Доставлено: <b>{sent}</b>\n"
        f"• Ошибки: <b>{failed}</b>\n"
        f"• Всего: <b>{total}</b>",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )


# ===========================
# 📢 Рассылка — По ID
# ===========================

@router.callback_query(F.data == "broadcast_by_id", F.from_user.id.in_(ADMIN_IDS))
async def broadcast_by_id_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.broadcast_ids)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")]
    ])
    await callback.message.edit_text(
        "🎯 <b>Рассылка по ID</b>\n\n"
        "Введи один или несколько Telegram ID через запятую или пробел:\n\n"
        "<i>Пример: <code>123456789, 987654321, 111222333</code></i>",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(AdminStates.broadcast_ids, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_by_id_got_ids(message: Message, state: FSMContext):
    raw = message.text.strip()

    # Парсим все числа из строки
    id_strings = re.findall(r'\d+', raw)
    if not id_strings:
        await message.answer(
            "❌ Не найдено ни одного ID. Введи числа через запятую или пробел:"
        )
        return

    target_ids = list(set(int(x) for x in id_strings))  # убираем дубли
    await state.update_data(broadcast_target_ids=target_ids)
    await state.set_state(AdminStates.broadcast_text_ids)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast")]
    ])
    ids_preview = ", ".join(str(x) for x in target_ids[:10])
    if len(target_ids) > 10:
        ids_preview += f" и ещё {len(target_ids) - 10}..."

    await message.answer(
        f"✅ Получателей: <b>{len(target_ids)}</b>\n"
        f"<code>{ids_preview}</code>\n\n"
        "Теперь введи текст сообщения:\n"
        "<i>Поддерживается HTML: <b>жирный</b>, <i>курсив</i>, <code>код</code></i>",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(AdminStates.broadcast_text_ids, F.from_user.id.in_(ADMIN_IDS))
async def broadcast_by_id_send(message: Message, state: FSMContext, bot: Bot):
    text = message.html_text or message.text or ""
    if not text.strip():
        await message.answer("❌ Пустое сообщение.")
        return

    data = await state.get_data()
    target_ids = data.get("broadcast_target_ids", [])
    await state.clear()

    if not target_ids:
        await message.answer("❌ Список ID пуст. Начни заново.")
        return

    status_msg = await message.answer(
        f"📤 Отправляю на <b>{len(target_ids)}</b> адресов...",
        parse_mode='HTML'
    )

    sent, failed, not_found = 0, 0, []
    for uid in target_ids:
        try:
            await bot.send_message(uid, text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
            not_found.append(uid)
        await asyncio.sleep(0.05)  # небольшая пауза между запросами

    failed_text = ""
    if not_found:
        ids_str = ", ".join(str(x) for x in not_found[:15])
        if len(not_found) > 15:
            ids_str += f" и ещё {len(not_found) - 15}..."
        failed_text = f"\n\n⚠️ <b>Не доставлено:</b>\n<code>{ids_str}</code>"

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"• Доставлено: <b>{sent}</b>\n"
        f"• Ошибки: <b>{failed}</b>"
        f"{failed_text}",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )


# ===========================
# Noop / заглушка
# ===========================

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


# ============================================================
# Групповой чат — управление (вкл/выкл)
# Добавьте кнопку в admin_panel в user_kb.py:
# [InlineKeyboardButton(text="🤖 Групповой чат", callback_data="admin_group_chat")]
# ============================================================
from handlers.group_chat import set_group_chat_enabled, is_group_chat_enabled, group_settings
 
 
@router.callback_query(F.data == "admin_group_chat", F.from_user.id.in_(ADMIN_IDS))
async def admin_group_chat_menu(callback: CallbackQuery):
    await callback.answer()

    groups = []
    async for doc in group_settings.find({}):
        groups.append(doc)

    text = "🤖 <b>Групповой ИИ-чат</b>\n\n"
    if not groups:
        text += (
            "Ни одна группа пока не зарегистрирована.\n\n"
            "<b>Как зарегистрировать группу:</b>\n"
            "1. Добавьте бота в группу (он зарегистрируется автоматически)\n"
            "2. Или отправьте в группе команду: <code>/reg_group</code>\n\n"
            "<i>После регистрации группа появится здесь.</i>"
        )
    else:
        text += "✅ — вкл  |  ❌ — выкл  |  🦥 — настроить лень\n\n"
        for g in groups:
            st    = "✅ Вкл" if g.get("enabled") else "❌ Выкл"
            title = g.get("chat_title") or str(g["chat_id"])
            laz   = g.get("laziness", 60)
            text += f"• <b>{title}</b>  {st} · Лень: {laz}%\n"

    buttons = []
    for g in groups:
        title   = (g.get("chat_title") or str(g["chat_id"]))[:22]
        enabled = g.get("enabled", False)
        laz     = g.get("laziness", 60)
        cid     = g["chat_id"]
        buttons.append([
            InlineKeyboardButton(
                text=f"{'🔴 Выкл' if enabled else '🟢 Вкл'} {title}",
                callback_data=f"gc_toggle_{cid}"
            ),
            InlineKeyboardButton(
                text=f"🦥 {laz}%",
                callback_data=f"gc_lazy_{cid}"
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"gc_del_{cid}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")])
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode='HTML'
    )
 
@router.callback_query(F.data.startswith("gc_toggle_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_gc_toggle(callback: CallbackQuery):
    chat_id = int(callback.data.replace("gc_toggle_", ""))
    current = await is_group_chat_enabled(chat_id)
    new     = not current
    await set_group_chat_enabled(chat_id, new)
    await callback.answer(f"{'✅ Включён' if new else '❌ Выключен'}")
    await admin_group_chat_menu(callback)

@router.callback_query(F.data.startswith("gc_lazy_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_gc_lazy_menu(callback: CallbackQuery):
    chat_id = int(callback.data.replace("gc_lazy_", ""))
    doc = await group_settings.find_one({"chat_id": chat_id})
    current = doc.get("laziness", 60)
    title = doc.get("chat_title") or str(chat_id)

    levels = [0, 20, 40, 60, 80, 95]
    rows = []
    row = []
    for val in levels:
        mark = "✅ " if val == current else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{val}%",
            callback_data=f"gc_setlazy_{chat_id}_{val}"
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_group_chat")])

    await callback.message.edit_text(
        f"🦥 <b>Лень для «{title}»</b>\n\n"
        f"Текущее значение: <b>{current}%</b>\n\n"
        "0% → отвечает на каждое сообщение\n"
        "60% → примерно каждое 3-е\n"
        "95% → почти молчит, только @упоминания",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gc_setlazy_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_gc_set_laziness(callback: CallbackQuery):
    # gc_setlazy_CHATID_VALUE
    parts   = callback.data.split("_")
    chat_id = int(parts[2])
    value   = int(parts[3])

    await group_settings.update_one(
        {"chat_id": chat_id},
        {"$set": {"laziness": value}}
    )
    await callback.answer(f"✅ Лень: {value}%")

    # Возвращаемся в меню лени с обновлённым значением
    doc   = await group_settings.find_one({"chat_id": chat_id})
    title = doc.get("chat_title") or str(chat_id)

    levels = [0, 20, 40, 60, 80, 95]
    rows = []
    row = []
    for val in levels:
        mark = "✅ " if val == value else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{val}%",
            callback_data=f"gc_setlazy_{chat_id}_{val}"
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_group_chat")])

    await callback.message.edit_text(
        f"🦥 <b>Лень для «{title}»</b>\n\n"
        f"Текущее значение: <b>{value}%</b>\n\n"
        "0% → отвечает на каждое сообщение\n"
        "60% → примерно каждое 3-е\n"
        "95% → почти молчит, только @упоминания",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode='HTML'
    )
 
# ============================================================
# Статистика с разбивкой по типам оплаты
# ============================================================
@router.callback_query(F.data == "admin_statistics", F.from_user.id.in_(ADMIN_IDS))
async def admin_statistics_menu(callback: CallbackQuery):
    await callback.answer()
    from database.stats_models import stats_users, stats_finance
    from database.billing_models import payments
 
    u = await stats_users()
    f = await stats_finance()
 
    # Разбивка по типам оплаты
    by = {"rub": 0.0, "stars": 0.0, "crypto": 0.0, "rub_c": 0, "stars_c": 0, "crypto_c": 0}
    async for p in payments.find({"status": "succeeded"}):
        t   = str(p.get("type", p.get("currency", "rub"))).lower()
        amt = float(p.get("amount_rub", p.get("amount", 0)))
        if "xtr" in t or "stars" in t:
            by["stars"] += amt; by["stars_c"] += 1
        elif "usdt" in t or "crypto" in t:
            by["crypto"] += amt; by["crypto_c"] += 1
        else:
            by["rub"] += amt; by["rub_c"] += 1
 
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        "<b>👥 Пользователи:</b>\n"
        f"• Всего: <code>{u['total']}</code>\n"
        f"• С подпиской: <code>{u['with_sub']}</code>\n"
        f"• Без подписки: <code>{u['no_sub']}</code>\n"
        f"• Сегодня: <code>{u['new_today']}</code>\n"
        f"• За неделю: <code>{u['new_week']}</code>\n"
        f"• За месяц: <code>{u['new_month']}</code>\n\n"
        "<b>💰 Финансы:</b>\n"
        f"• Всего: <code>{f['total_revenue']:.0f}₽</code>\n"
        f"• За месяц: <code>{f['month_revenue']:.0f}₽</code>\n"
        f"• Сегодня: <code>{f['today_revenue']:.0f}₽</code>\n"
        f"• Платежей: <code>{f['payment_count']}</code>\n"
        f"• Активных подписок: <code>{f['active_subs']}</code>\n\n"
        "<b>💳 По способу оплаты:</b>\n"
        f"• 💳 Рублями (ЮКасса): <code>{by['rub']:.0f}₽</code> ({by['rub_c']} шт.)\n"
        f"• ⭐ Telegram Stars:    <code>{by['stars']:.0f}₽</code> ({by['stars_c']} шт.)\n"
        f"• ₮ Крипто (USDT):     <code>{by['crypto']:.0f}₽</code> ({by['crypto_c']} шт.)"
    )
 
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Топ XP",    callback_data="stats_top_xp"),
         InlineKeyboardButton(text="📊 Активность", callback_data="stats_activity")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@router.callback_query(F.data.startswith("gc_del_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_gc_delete_confirm(callback: CallbackQuery):
    chat_id = int(callback.data.replace("gc_del_", ""))
    doc = await group_settings.find_one({"chat_id": chat_id})
    title = doc.get("chat_title") or str(chat_id)

    await callback.message.edit_text(
        f"🗑 <b>Удалить группу?</b>\n\n"
        f"«{title}»\n\n"
        f"Группа будет удалена из базы. Бот останется в группе, "
        f"но перестанет реагировать на сообщения до повторной регистрации.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"gc_delok_{chat_id}"),
                InlineKeyboardButton(text="❌ Отмена",      callback_data="admin_group_chat")
            ]
        ]),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gc_delok_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_gc_delete_do(callback: CallbackQuery):
    chat_id = int(callback.data.replace("gc_delok_", ""))
    await group_settings.delete_one({"chat_id": chat_id})
    await callback.answer("🗑 Группа удалена")
    # Возвращаемся в список
    await admin_group_chat_menu(callback)

# ===========================
# МЕНЮ АДМИН-ПАНЕЛИ (СГРУППИРОВАННОЕ)
# ===========================

@router.callback_query(F.data == "admin_plans_promos", F.from_user.id.in_(ADMIN_IDS))
async def admin_plans_promos_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📦 <b>Тарифы и промокоды</b>\nВыберите действие:",
        reply_markup=kb.admin_plans_promos,
        parse_mode='HTML'
    )

@router.callback_query(F.data == "admin_users_menu", F.from_user.id.in_(ADMIN_IDS))
async def admin_users_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "👤 <b>Управление пользователями</b>\nВыберите действие:",
        reply_markup=kb.admin_users_menu,
        parse_mode='HTML'
    )