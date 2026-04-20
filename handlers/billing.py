"""
handlers/billing.py

Кошелёк, пополнение через ЮKassa, активация тарифа с промокодом.

Подключение вебхука в main.py:
    from aiohttp import web
    from handlers.billing import yookassa_webhook
    app = web.Application()
    app.router.add_post("/yookassa/webhook", yookassa_webhook)
    web.run_app(app, port=8080)  # или используй aiogram webhook

Переменные окружения (.env):
    YOOKASSA_SHOP_ID=...
    YOOKASSA_SECRET_KEY=...
    BOT_BASE_URL=https://yourdomain.com   # публичный URL для return_url
"""

import os
import uuid
import aiohttp
from datetime import datetime

from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiohttp import web
from dotenv import load_dotenv
from database.billing_models import has_used_trial, activate_trial, payments

import keyboards.user_kb as kb
from database.billing_models import (
    get_wallet, get_balance, top_up_balance, deduct_balance,
    get_all_plans, get_plan,
    get_promo_by_code, use_promo,
    get_active_subscription, has_active_subscription, activate_subscription,
    save_payment, get_payment_by_id, update_payment_status
)

load_dotenv()

router = Router()

YOOKASSA_SHOP_ID   = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET    = os.getenv("YOOKASSA_SECRET_KEY", "")
BOT_BASE_URL       = os.getenv("BOT_BASE_URL", "https://yourdomain.com")

# Минимальная сумма пополнения (ЮKassa не принимает < 1 руб)
MIN_TOPUP = 10


# ===========================
# FSM
# ===========================

class BillingStates(StatesGroup):
    waiting_topup_amount  = State()   # Ввод суммы пополнения
    waiting_promo_code    = State()   # Ввод промокода
    waiting_stars_amount = State()
    waiting_crypto_amount = State()


# ===========================
# Клавиатуры
# ===========================

def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Пополнить кошелёк", callback_data="wallet_topup_select")],
        [InlineKeyboardButton(text="📦 Купить тариф", callback_data="wallet_buy_plan")],
        [InlineKeyboardButton(text="🎁 Пробный период", callback_data="trial_activate")],
        [InlineKeyboardButton(text="📤 Вывод средств", callback_data="wallet_withdraw")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="personal")],
    ])


def plans_kb(plans: list) -> InlineKeyboardMarkup:
    buttons = []
    for plan in plans:
        label = f"🔹 {plan['name']} — {plan['price']}₽ / {plan['duration_days']} дн."
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"buy_plan_{plan['_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_view")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_plan_kb(plan_id: str, final_price: float, has_promo: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"✅ Оплатить {final_price}₽",
            callback_data=f"confirm_plan_{plan_id}"
        )],
    ]
    if not has_promo:
        buttons.append([InlineKeyboardButton(
            text="🎟 Ввести промокод",
            callback_data=f"enter_promo_{plan_id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_buy_plan")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stars_packages_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 50", callback_data="stars_50")],
        [InlineKeyboardButton(text="⭐ 100", callback_data="stars_100")],
        [InlineKeyboardButton(text="⭐ 170", callback_data="stars_170")],
        [InlineKeyboardButton(text="⭐ 500", callback_data="stars_500")],
        [InlineKeyboardButton(text="✏️ Ввести свою сумму", callback_data="stars_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_topup_select")]
    ])

# ===========================
# Команда /wallet
# ===========================
async def show_wallet(event, state: FSMContext):
    await state.clear()

    # Определяем тип (Message или CallbackQuery)
    if isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        message = event.message
        await event.answer()
        is_callback = True
    else:
        user_id = event.from_user.id
        message = event
        is_callback = False

    balance = await get_balance(user_id)
    sub = await get_active_subscription(user_id)

    if sub:
        expires = datetime.fromisoformat(sub["expires_at"])
        delta = expires - datetime.now()
        days_left = max(0, delta.days)

        sub_text = (
            f"\n\n🟢 <b>Тариф:</b> {sub['plan_name']}\n"
            f"⏳ <b>Осталось:</b> {days_left} дн. (до {expires.strftime('%d.%m.%Y')})"
        )
    else:
        sub_text = "\n\n🔴 <b>Тариф:</b> не активен"

    text = (
        f"💼 <b>Мой кошелёк</b>\n\n"
        f"💰 <b>Баланс:</b> {balance:.2f}₽"
        f"{sub_text}"
    )

    # Универсальная отправка
    if is_callback:
        await message.edit_text(
            text,
            reply_markup=wallet_kb(),
            parse_mode='HTML'
        )
    else:
        await message.answer(
            text,
            reply_markup=wallet_kb(),
            parse_mode='HTML'
        )

from middlewares.subscription_check import check_sub

@router.message(Command("wallet"))
async def wallet_command(message: Message, state: FSMContext):
    if not await check_sub(message.from_user.id, message):
        return
    await show_wallet(message, state)


# ===========================
# Просмотр кошелька
# ===========================

@router.callback_query(F.data == "wallet_view")
async def view_wallet(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    user_id = callback.from_user.id

    balance = await get_balance(user_id)
    sub = await get_active_subscription(user_id)

    sub_text = ""
    if sub:
        expires = datetime.fromisoformat(sub["expires_at"])
        delta = expires - datetime.now()
        days_left = max(0, delta.days)
        sub_text = (
            f"\n\n🟢 <b>Тариф:</b> {sub['plan_name']}\n"
            f"⏳ <b>Осталось:</b> {days_left} дн. (до {expires.strftime('%d.%m.%Y')})"
        )
    else:
        sub_text = "\n\n🔴 <b>Тариф:</b> не активен"

    await callback.message.edit_text(
        f"💼 <b>Мой кошелёк</b>\n\n"
        f"💰 <b>Баланс:</b> {balance:.2f}₽"
        f"{sub_text}",
        reply_markup=wallet_kb(),
        parse_mode='HTML'
    )


# ===========================
# Выбор способа оплаты
# ===========================

@router.callback_query(F.data == "wallet_topup_select")
async def choose_payment_method(callback: CallbackQuery):
    await callback.answer()

    wallet_topup_select = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data="wallet_topup")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="topup_stars")],
        [InlineKeyboardButton(text="🪙 Crypto (USDT)", callback_data="topup_crypto")],
    ])

    await callback.message.edit_text(
        "💳 Выберите способ оплаты:",
        reply_markup=wallet_topup_select
    )


# ===========================
# Telegram Stars
# ===========================
from services.rates import stars_to_rub

@router.callback_query(F.data == "topup_stars")
async def stars_menu(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        "⭐ Выберите пакет или введите свою сумму:",
        reply_markup=stars_packages_kb()
    )

@router.callback_query(F.data == "stars_custom")
async def stars_custom(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BillingStates.waiting_stars_amount)

    await callback.message.edit_text(
        "⭐ Введите количество Stars:"
    )


@router.callback_query(F.data.startswith("stars_"))
async def stars_package_handler(callback: CallbackQuery, bot: Bot):
    await callback.answer()

    if callback.data == "stars_custom":
        return

    stars = int(callback.data.split("_")[1])

    from services.rates import stars_to_rub
    rub = await stars_to_rub(stars)

    from aiogram.types import LabeledPrice

    # ✅ Для Telegram Stars: amount = кол-во звёзд БЕЗ умножения на 100
    prices = [LabeledPrice(label="Пополнение", amount=stars)]

    payment_id = f"stars_{callback.from_user.id}_{stars}"
    rate = rub / stars if stars else 0

    await save_payment(
        user_id=callback.from_user.id,
        payment_id=payment_id,
        amount=rub,
        status="pending",
        payment_type="stars",
        original_amount=stars,
        currency="XTR",
        rate=rate
    )

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Пополнение баланса",
        description=f"{stars} ⭐ ≈ {rub:.2f} ₽",
        payload=payment_id,
        provider_token="",
        currency="XTR",
        prices=prices
    )

@router.message(BillingStates.waiting_stars_amount)
async def stars_amount_entered(message: Message, state: FSMContext, bot: Bot):
    try:
        stars = float(message.text)
    except:
        await message.answer("❌ Введите число")
        return

    if stars <= 0:
        await message.answer("❌ Минимум 1 Star")
        return
    if stars > 1500:
        await message.answer("❌ Слишком большая сумма")
        return

    rub = await stars_to_rub(stars)

    await state.clear()

    from aiogram.types import LabeledPrice

    # ✅ Для Telegram Stars: amount = кол-во звёзд БЕЗ умножения на 100
    stars_int = int(stars)
    prices = [LabeledPrice(label="Пополнение", amount=stars_int)]

    rate = rub / stars if stars else 0
    payment_id = f"stars_{message.from_user.id}_{stars_int}"

    await save_payment(
        user_id=message.from_user.id,
        payment_id=payment_id,
        amount=rub,
        status="pending",
        payment_type="stars",
        original_amount=stars_int,
        currency="XTR",
        rate=rate
    )

    await bot.send_invoice(
        chat_id=message.from_user.id,
        title="Пополнение баланса",
        description=f"{stars_int} ⭐ ≈ {rub:.2f} ₽",
        payload=payment_id,
        provider_token="",
        currency="XTR",
        prices=prices
    )

from aiogram.types import PreCheckoutQuery

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """
    Telegram обязательно требует ответа на pre_checkout_query.
    Без этого кнопка оплаты будет заблокирована.
    """
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def stars_success(message: Message, bot: Bot):
    payload = message.successful_payment.invoice_payload

    if not payload.startswith("stars_"):
        return

    # payload формат: stars_{user_id}_{stars}
    payment_id = payload

    # Идемпотентность — не зачисляем дважды
    payment = await get_payment_by_id(payment_id)
    if payment and payment.get("credited"):
        return

    # Парсим кол-во звёзд из payload: stars_{user_id}_{stars}
    parts = payload.split("_")
    stars = int(parts[-1])  # последний элемент — количество звёзд

    rub = await stars_to_rub(stars)

    user_id = message.from_user.id
    await top_up_balance(user_id, rub)
    await update_payment_status(payment_id, "paid")
    await payments.update_one(
        {"payment_id": payment_id},
        {"$set": {"credited": True}}
    )

    # XP за пополнение
    try:
        from services.xp import give_xp
        await give_xp(bot, user_id, "wallet_topup")
    except Exception:
        pass

    # Уведомление пользователю
    try:
        photo = FSInputFile("media/notifications/notification_replenishment_wallet.png")
        await bot.send_photo(
            user_id,
            photo=photo,
            caption=(
                f"✅ <b>Кошелёк пополнен!</b>\n\n"
                f"⭐ Звёзд: <b>{stars}</b>\n"
                f"💰 Зачислено: <b>{rub:.2f} ₽</b>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Stars notify error: {e}")


# ===========================
# Crypto (USDT)
# ===========================

from services.rates import usdt_to_rub

@router.callback_query(F.data == "topup_crypto")
async def crypto_input(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BillingStates.waiting_crypto_amount)

    await callback.message.edit_text(
        "🪙 Введите сумму в USDT:"
    )

from services.crypto import create_crypto_invoice

@router.message(BillingStates.waiting_crypto_amount)
async def crypto_amount_entered(message: Message, state: FSMContext):
    try:
        usdt = float(message.text)
    except:
        await message.answer("❌ Введите число")
        return

    if usdt <= 0:
        await message.answer("❌ Минимум 1 USDT")
        return
    if usdt > 50:
        await message.answer("❌ Слишком большая сумма")
        return

    rub = await usdt_to_rub(usdt)

    invoice = await create_crypto_invoice(usdt, message.from_user.id)

    pay_url = invoice["pay_url"]
    invoice_id = invoice["invoice_id"]

    # сохраняем платеж
    rate = rub / usdt

    await save_payment(
        user_id=message.from_user.id,
        payment_id=str(invoice_id),
        amount=rub,
        status="pending",
        payment_type="crypto",
        original_amount=usdt,
        currency="USDT",
        rate=rate
    )

    await state.clear()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_crypto_{invoice_id}")]
    ])

    await message.answer(
        f"🪙 {usdt} USDT ≈ {rub:.2f} ₽\n\n"
        f"После оплаты нажмите кнопку ниже 👇",
        reply_markup=kb
    )

from services.crypto import is_crypto_paid

@router.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto(callback: CallbackQuery):
    await callback.answer()

    invoice_id = callback.data.replace("check_crypto_", "")

    paid = await is_crypto_paid(invoice_id)

    if not paid:
        await callback.answer("❌ Оплата не найдена", show_alert=True)
        return

    payment = await get_payment_by_id(invoice_id)

    if payment.get("credited"):
        await callback.answer("⚠️ Уже зачислено", show_alert=True)
        return

    await top_up_balance(
        payment["user_id"],
        payment["amount_rub"]
    )

    await update_payment_status(invoice_id, "paid")

    await payments.update_one(
        {"payment_id": invoice_id},
        {"$set": {"credited": True}}
    )

    # 💰 зачисляем
    await top_up_balance(
        payment["user_id"],
        payment["amount_rub"]
    )

    await update_payment_status(invoice_id, "paid")

    await payments.update_one(
        {"payment_id": invoice_id},
        {"$set": {"credited": True}}
    )

    # 🎯 XP (как у других оплат)
    try:
        from services.xp import give_xp
        await give_xp(callback.bot, payment["user_id"], "wallet_topup")
    except Exception:
        pass

    # 📸 КАРТИНКА (как у Stars и ЮKassa)
    photo = FSInputFile("media/notifications/notification_replenishment_wallet.png")

    await callback.bot.send_photo(
        chat_id=payment["user_id"],
        photo=photo,
        caption=(
            f"✅ <b>Кошелёк пополнен!</b>\n\n"
            f"🪙 USDT: <b>{payment['original_amount']}</b>\n"
            f"💰 Зачислено: <b>{payment['amount_rub']:.2f} ₽</b>"
        ),
        parse_mode="HTML"
    )

    # ❌ убираем старое сообщение
    await callback.message.edit_text("✅ Оплата успешно подтверждена!")


# ===========================
# Пополнение — ввод суммы
# ===========================

@router.callback_query(F.data == "wallet_topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BillingStates.waiting_topup_amount)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_view")]
    ])
    await callback.message.edit_text(
        f"💳 <b>Пополнение кошелька</b>\n\n"
        f"Введите сумму в рублях (минимум {MIN_TOPUP}₽):",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(BillingStates.waiting_topup_amount, F.text)
async def topup_amount_received(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите корректную сумму, например: <code>200</code>", parse_mode='HTML')
        return

    if amount < MIN_TOPUP:
        await message.answer(f"❌ Минимальная сумма пополнения — {MIN_TOPUP}₽")
        return

    await state.clear()

    user_id = message.from_user.id
    payment_id = str(uuid.uuid4())

    # Создаём платёж в ЮKassa
    payment_url = await create_yookassa_payment(
        amount=amount,
        payment_id=payment_id,
        description=f"Пополнение кошелька MathTutor (user {user_id})"
    )

    if not payment_url:
        await message.answer(
            "❌ Не удалось создать платёж. Попробуйте позже.",
            reply_markup=wallet_kb()
        )
        return

    # Сохраняем в БД как pending
    await save_payment(user_id, payment_id, amount, "pending")

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="⬅️ В кошелёк",  callback_data="wallet_view")],
    ])

    await message.answer(
        f"💳 <b>Счёт на оплату</b>\n\n"
        f"Сумма: <b>{amount:.0f}₽</b>\n\n"
        f"После оплаты средства автоматически зачислятся на кошелёк.\n"
        f"Нажмите кнопку ниже для перехода к оплате:",
        reply_markup=pay_kb,
        parse_mode='HTML'
    )


# ===========================
# Тарифы — список
# ===========================

@router.callback_query(F.data == "wallet_buy_plan")
async def show_plans(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    all_plans = await get_all_plans()
    if not all_plans:
        await callback.message.edit_text(
            "📭 Тарифов пока нет. Обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_view")]
            ])
        )
        return

    await callback.message.edit_text(
        "📦 <b>Доступные тарифы</b>\n\nВыберите тариф для активации:",
        reply_markup=plans_kb(all_plans),
        parse_mode='HTML'
    )


# ===========================
# Тариф — карточка + промокод
# ===========================

@router.callback_query(F.data.startswith("buy_plan_"))
async def plan_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    plan_id = callback.data.replace("buy_plan_", "")
    plan = await get_plan(plan_id)

    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    # Проверяем, есть ли уже применённый промокод в FSM
    data = await state.get_data()
    promo = data.get(f"promo_{plan_id}")
    discount = promo["discount_percent"] if promo else 0
    final_price = round(plan["price"] * (1 - discount / 100), 2)

    desc = plan.get("description", "")
    promo_text = f"\n🎟 Промокод: <b>-{discount}%</b>" if discount else ""

    text = (
        f"📦 <b>{plan['name']}</b>\n\n"
        f"{desc}\n\n" if desc else f"📦 <b>{plan['name']}</b>\n\n"
    )
    text += (
        f"💰 Цена: <b>{plan['price']}₽</b>{promo_text}\n"
        f"{'✅ К оплате: <b>' + str(final_price) + '₽</b>' if discount else ''}\n"
        f"📅 Срок: <b>{plan['duration_days']} дней</b>"
    )

    balance = await get_balance(callback.from_user.id)
    text += f"\n\n💼 Ваш баланс: <b>{balance:.2f}₽</b>"

    if balance < final_price:
        text += f"\n⚠️ Недостаточно средств. Пополните кошелёк."

    await callback.message.edit_text(
        text,
        reply_markup=confirm_plan_kb(plan_id, final_price, bool(promo)),
        parse_mode='HTML'
    )


# ===========================
# Ввод промокода
# ===========================

@router.callback_query(F.data.startswith("enter_promo_"))
async def enter_promo_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    plan_id = callback.data.replace("enter_promo_", "")
    await state.update_data(promo_for_plan=plan_id)
    await state.set_state(BillingStates.waiting_promo_code)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"buy_plan_{plan_id}")]
    ])
    await callback.message.edit_text(
        "🎟 <b>Введите промокод:</b>",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.message(BillingStates.waiting_promo_code, F.text)
async def promo_code_received(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    plan_id = data.get("promo_for_plan")

    promo = await get_promo_by_code(code)

    if not promo:
        await message.answer(
            "❌ Промокод не найден или недействителен. Попробуйте ещё раз:"
        )
        return

    # Сохраняем промокод в FSM для этого тарифа
    await state.update_data(**{f"promo_{plan_id}": promo})
    await state.set_state(None)

    await message.answer(
        f"✅ Промокод <b>{promo['code']}</b> применён!\n"
        f"Скидка: <b>{promo['discount_percent']}%</b>",
        parse_mode='HTML'
    )

    # Возвращаем карточку тарифа с обновлённой ценой
    plan = await get_plan(plan_id)
    if not plan:
        return

    discount = promo["discount_percent"]
    final_price = round(plan["price"] * (1 - discount / 100), 2)
    balance = await get_balance(message.from_user.id)

    text = (
        f"📦 <b>{plan['name']}</b>\n\n"
        f"💰 Цена: <b>{plan['price']}₽</b>\n"
        f"🎟 Промокод: <b>-{discount}%</b>\n"
        f"✅ К оплате: <b>{final_price}₽</b>\n"
        f"📅 Срок: <b>{plan['duration_days']} дней</b>\n\n"
        f"💼 Ваш баланс: <b>{balance:.2f}₽</b>"
    )
    if balance < final_price:
        text += f"\n⚠️ Недостаточно средств. Пополните кошелёк."

    await message.answer(
        text,
        reply_markup=confirm_plan_kb(plan_id, final_price, True),
        parse_mode='HTML'
    )


# ===========================
# Подтверждение покупки тарифа
# ===========================

@router.callback_query(F.data.startswith("confirm_plan_"))
async def confirm_plan_purchase(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    plan_id = callback.data.replace("confirm_plan_", "")
    user_id = callback.from_user.id

    plan = await get_plan(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    data = await state.get_data()
    promo = data.get(f"promo_{plan_id}")
    discount = promo["discount_percent"] if promo else 0
    final_price = round(plan["price"] * (1 - discount / 100), 2)

    # 💳 Списываем деньги
    ok = await deduct_balance(user_id, final_price)
    if not ok:
        balance = await get_balance(user_id)
        await callback.message.edit_text(
            f"❌ <b>Недостаточно средств</b>\n\n"
            f"Требуется: <b>{final_price}₽</b>\n"
            f"На балансе: <b>{balance:.2f}₽</b>\n\n"
            f"Пополните кошелёк и попробуйте снова.",
            reply_markup=wallet_kb(),
            parse_mode='HTML'
        )
        return

    # 🎟 Промокод
    if promo:
        await use_promo(promo["code"], callback.from_user.id)


    # 🚀 Активируем подписку
    await activate_subscription(
        user_id=user_id,
        plan_id=plan_id,
        duration_days=plan["duration_days"],
        plan_name=plan["name"],
        price=plan["price"]
    )

    sub = await get_active_subscription(user_id)
    expires = datetime.fromisoformat(sub["expires_at"])

    await state.clear()

    # 🔥 КАРТИНКА (главное)
    from aiogram.types import FSInputFile
    photo = FSInputFile("media/notifications/notification_buy_subscription.png")

    await callback.bot.send_photo(
        chat_id=user_id,
        photo=photo,
        caption=(
            f"🎉 <b>Тариф «{plan['name']}» активирован!</b>\n\n"
            f"💳 Списано: <b>{final_price}₽</b>\n"
            f"📅 Действует до: <b>{expires.strftime('%d.%m.%Y')}</b>\n\n"
            f"Теперь вам доступны все функции бота!"
        ),
        parse_mode='HTML'
    )

    # 📲 Обновляем интерфейс (оставляем)
    await callback.message.edit_text(
        "✅ <b>Тариф успешно активирован!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 Мой кошелёк", callback_data="wallet_view")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")],
        ]),
        parse_mode='HTML'
    )


# ===========================
# Вывод средств
# ===========================

@router.callback_query(F.data == "wallet_withdraw")
async def wallet_withdraw(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📤 <b>Вывод средств</b>\n\n"
        "Для вывода средств с кошелька обратитесь к администратору:\n"
        "@admin_username",  # ← замените на реальный юзернейм
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_view")]
        ]),
        parse_mode='HTML'
    )


# ===========================
# ЮKassa: создание платежа
# ===========================

async def create_yookassa_payment(amount: float, payment_id: str, description: str) -> str | None:
    """Создаёт платёж в ЮKassa и возвращает URL для оплаты."""
    url = "https://api.yookassa.ru/v3/payments"
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"{BOT_BASE_URL}/payment-success"
        },
        "capture": True,
        "description": description,
        "metadata": {"payment_id": payment_id}
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                auth=aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET),
                headers={"Idempotence-Key": payment_id}
            ) as resp:
                data = await resp.json()
                print("YOOKASSA:", data)
                return data.get("confirmation", {}).get("confirmation_url")
    except Exception as e:
        print("YOOKASSA ERROR:", e)
        return None


# ===========================
# ЮKassa Webhook (aiohttp handler)
# ===========================

async def yookassa_webhook(request: web.Request, bot: Bot) -> web.Response:
    """
    POST /yookassa/webhook
    Принимает уведомления от ЮKassa о статусе платежей.
    Регистрируется в main.py в aiohttp-приложении.
    """
    print("🔥 WEBHOOK ПРИШЕЛ")
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400)

    event = body.get("event")
    obj   = body.get("object", {})

    if event != "payment.succeeded":
        return web.Response(status=200)

    yookassa_payment_id = obj.get("id")
    amount_data = obj.get("amount", {})
    amount = float(amount_data.get("value", 0))
    metadata = obj.get("metadata", {})
    our_payment_id = metadata.get("payment_id")

    if not our_payment_id:
        return web.Response(status=200)

    # Проверяем — не обрабатывали ли уже
    existing = await get_payment_by_id(our_payment_id)
    if not existing:
        return web.Response(status=200)

    if existing.get("status") == "succeeded":
        return web.Response(status=200)  # идемпотентность

    # Зачисляем деньги
    user_id = existing["user_id"]
    await top_up_balance(user_id, amount)

    try:
        from services.xp import give_xp
        await give_xp(bot, user_id, "wallet_topup")
    except Exception:
        pass

    await update_payment_status(our_payment_id, "succeeded")

    # Уведомляем пользователя
    # bot передаётся через app["bot"] в main.py
    bot: Bot = request.app.get("bot")
    photo = FSInputFile("media/notifications/notification_replenishment_wallet.png")
    if bot:
        try:
            # await bot.send_sticker(
            #     chat_id=user_id,
            #     sticker="CAACAgIAAxkBAAFG27Vp2C6_dKdMZFcMIaLXlAtVzhYQTQACqpUAAkaOwUqS3PLOvG5XhTsE"
            # )
            await bot.send_photo(
                user_id,
                photo=photo,
                caption=f"✅ <b>Кошелёк пополнен на {amount:.0f}₽!</b>\n\n"
                f"Средства зачислены и доступны для оплаты тарифа.",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Webhook notify error: {e}")

    return web.Response(status=200)


# =============================================

@router.callback_query(F.data == "trial_activate")
async def trial_activate_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    from database.billing_models import (
        has_used_trial,
        activate_trial,
        has_real_subscription
    )

    # ❌ Уже есть активная подписка
    if await has_real_subscription(user_id):
        await callback.answer("❌ У тебя уже есть активная подписка", show_alert=True)
        return

    # ❌ Уже использовал trial
    if await has_used_trial(user_id):
        await callback.answer("❌ Вы уже активировали пробный период ранее", show_alert=True)
        return

    # ✅ Активируем trial
    await activate_trial(user_id)

    await callback.message.edit_text(
        "🎉 <b>Пробный период активирован!</b>\n\n"
        "⏳ Доступ на <b>2 дня</b>\n"
        "После этого потребуется подписка.",
        parse_mode='HTML'
    )

    await callback.answer()