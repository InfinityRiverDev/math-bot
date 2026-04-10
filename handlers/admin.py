"""
handlers/admin.py

Добавлено:
- Управление тарифами (создать / редактировать / удалить)
- Управление промокодами (создать / удалить)
- Рассылка всем пользователям
"""

import asyncio
import os

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
    # Редактирование тарифа
    edit_plan_field   = State()
    edit_plan_value   = State()
    # Промокоды
    promo_code        = State()
    promo_discount    = State()
    promo_max_uses    = State()
    # Рассылка
    broadcast_text    = State()


def is_admin(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


# ===========================
# Главное меню админа
# ===========================

@router.callback_query(F.data == "admin_main", F.from_user.id.in_(ADMIN_IDS))
async def admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛠 <b>Панель управления администратора</b>\nВыберите действие:",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_home(callback: CallbackQuery):
    is_admin_check = callback.from_user.id in ADMIN_IDS
    has_sub = await has_active_subscription(callback.from_user.id)

    if is_admin_check or has_sub:
        reply_markup = kb.get_start_kb(is_admin_check)
    else:
        reply_markup = kb.get_locked_kb(is_admin_check)

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


# ===========================
# Чистая прибыль
# ===========================

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
        f"• Цена подписки - 300₽\n• Цена API - 1500₽\n• Цена хостинга - 500₽\n\n"
        f"<b>Чистая прибыль:</b> <code>{profit}₽</code>\n"
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
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
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
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"admin_plan_edit_{plan_id}_name")],
        [InlineKeyboardButton(text="✏️ Изменить цену",    callback_data=f"admin_plan_edit_{plan_id}_price")],
        [InlineKeyboardButton(text="✏️ Изменить срок",    callback_data=f"admin_plan_edit_{plan_id}_duration_days")],
        [InlineKeyboardButton(text="✏️ Изменить описание",callback_data=f"admin_plan_edit_{plan_id}_description")],
        [InlineKeyboardButton(text="🗑 Удалить",           callback_data=f"admin_plan_del_{plan_id}")],
        [InlineKeyboardButton(text="⬅️ Назад",             callback_data="admin_plans")],
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
        "📦 <b>Новый тариф</b>\n\nВведите <b>название</b> тарифа:",
        parse_mode='HTML'
    )


@router.message(AdminStates.plan_name, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_name(message: Message, state: FSMContext):
    await state.update_data(plan_name=message.text.strip())
    await state.set_state(AdminStates.plan_price)
    await message.answer("💰 Введите <b>цену</b> в рублях (например: <code>200</code>):", parse_mode='HTML')


@router.message(AdminStates.plan_price, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число. Например: <code>200</code>", parse_mode='HTML')
        return
    await state.update_data(plan_price=price)
    await state.set_state(AdminStates.plan_duration)
    await message.answer("📅 Введите <b>срок действия</b> в днях (например: <code>30</code>):", parse_mode='HTML')


@router.message(AdminStates.plan_duration, F.from_user.id.in_(ADMIN_IDS))
async def admin_plan_duration(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите целое число дней.", parse_mode='HTML')
        return
    await state.update_data(plan_duration=days)
    await state.set_state(AdminStates.plan_description)
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="admin_plan_skip_desc")]
    ])
    await message.answer(
        "📝 Введите <b>описание</b> тарифа (или пропустите):",
        reply_markup=skip_kb,
        parse_mode='HTML'
    )


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
    plan_id = await create_plan(
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
    # формат: admin_plan_edit_{plan_id}_{field}
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
    await message.answer(
        f"✅ Поле обновлено.",
        reply_markup=await plans_admin_kb(),
        parse_mode='HTML'
    )


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
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_promos", F.from_user.id.in_(ADMIN_IDS))
async def admin_promos_list(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🎟 <b>Промокоды</b>",
        reply_markup=await promos_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Создание промокода
# ===========================

@router.callback_query(F.data == "admin_promo_create", F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_create_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.promo_code)
    await callback.message.edit_text(
        "🎟 <b>Новый промокод</b>\n\nВведите <b>код</b> (латиница/цифры, например: <code>SAVE20</code>):",
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
    await message.answer(
        f"💸 Введите <b>скидку в %</b> (1–99, например: <code>20</code>):",
        parse_mode='HTML'
    )


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
    await message.answer(
        "🔢 Введите <b>максимальное кол-во использований</b> (или без ограничений):",
        reply_markup=skip_kb,
        parse_mode='HTML'
    )


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
        f"✅ Промокод <b>{code}</b> создан!\n"
        f"Скидка: <b>{discount}%</b>\n{uses_text}",
        reply_markup=await promos_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Удаление промокода
# ===========================

@router.callback_query(F.data.startswith("admin_promo_del_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_promo_delete(callback: CallbackQuery):
    promo_id = callback.data.replace("admin_promo_del_", "")
    await delete_promo(promo_id)
    await callback.answer("🗑 Промокод удалён")
    await callback.message.edit_text(
        "🎟 <b>Промокоды</b>",
        reply_markup=await promos_admin_kb(),
        parse_mode='HTML'
    )


# ===========================
# Рассылка
# ===========================

@router.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.broadcast_text)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_main")]
    ])
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВведите текст сообщения.\n"
        "Поддерживается HTML-форматирование: <b>жирный</b>, <i>курсив</i>, <code>код</code>.",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(AdminStates.broadcast_text, F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    text = message.text or message.caption or ""
    if not text.strip():
        await message.answer("❌ Пустое сообщение.")
        return

    await state.clear()

    user_ids = await get_all_users()
    total = len(user_ids)
    status_msg = await message.answer(f"📢 Начинаю рассылку на {total} пользователей...")

    sent, failed = 0, 0
    for i, user_id in enumerate(user_ids, 1):
        try:
            await bot.send_message(user_id, text, parse_mode='HTML')
            sent += 1
        except Exception:
            failed += 1
        if i % 30 == 0:
            await asyncio.sleep(1)  # анти-флуд

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"• Доставлено: <b>{sent}</b>\n"
        f"• Ошибки: <b>{failed}</b>\n"
        f"• Всего: <b>{total}</b>",
        reply_markup=kb.admin_panel,
        parse_mode='HTML'
    )


# ===========================
# Управление лекциями (заглушка — основная логика в lectures.py)
# ===========================

@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()