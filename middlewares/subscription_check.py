"""
middlewares/subscription_check.py

Middleware — проверяет активную подписку у пользователя.
Если подписки нет — ограничивает доступ к функциям, 
оставляя доступными только «Личное» и «Услуги».

Подключение в main.py:
    from middlewares.subscription_check import SubscriptionMiddleware
    dp.update.middleware(SubscriptionMiddleware())
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message

from database.billing_models import has_active_subscription
from database.models import is_registered
from handlers.admin import ADMIN_IDS

# Callback-данные, разрешённые без подписки
ALLOWED_CALLBACKS = {
    # Навигация
    "back_to_main", "personal", "profile", "user_data",
    "backward_to_profile", "profile_view", "profile_delete",
    "profile_delete_confirm",
    # Услуги
    "services", "backward_to_services", "print",
    "paid_works", "backward_to_paid_works",
    "presentation", "backward_to_presentation",
    "pr_1", "pr_2", "pr_3", "pr_4", "pr_5",
    # Кошелёк и оплата — ВСЕГДА разрешены
    "wallet_view", "wallet_topup", "wallet_buy_plan", "wallet_withdraw",
    # Подписка
    "admin_main",  # администраторы
}

# Префиксы callback, разрешённые без подписки
ALLOWED_PREFIXES = (
    "buy_plan_",
    "confirm_plan_",
    "enter_promo_",
    "sched_cancel_",   # отмена в расписании (неважно)
    "check_ok_",
    "check_edit_",
    "policy_",
    "reg_",
    "order_pr_",
)

# Команды, всегда разрешённые
ALLOWED_COMMANDS = {"/start", "/cancel", "/help"}


LOCKED_MESSAGE = (
    "🔒 <b>Доступ ограничен</b>\n\n"
    "Для использования этой функции необходима активная подписка.\n\n"
    "Перейди в <b>Личное → Кошелёк</b>, пополни баланс и активируй тариф."
)


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None

        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        elif isinstance(event, Message):
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        # Администраторы — без ограничений
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        # Незарегистрированные — пускаем (registration сам разберётся)
        registered = await is_registered(user_id)
        if not registered:
            return await handler(event, data)

        # Проверка подписки
        has_sub = await has_active_subscription(user_id)
        if has_sub:
            return await handler(event, data)

        # — нет подписки —

        if isinstance(event, Message):
            text = (event.text or "").strip()
            # Разрешаем команды
            if any(text.startswith(cmd) for cmd in ALLOWED_COMMANDS):
                return await handler(event, data)
            # Разрешаем ввод данных в FSM (пусть handler сам решает)
            # Для этого проверяем есть ли активное FSM состояние
            state = data.get("state")
            if state:
                current = await state.get_state()
                if current:
                    return await handler(event, data)
            # Блокируем произвольные текстовые сообщения
            await event.answer(LOCKED_MESSAGE, parse_mode='HTML')
            return

        if isinstance(event, CallbackQuery):
            cb_data = event.data or ""

            if cb_data in ALLOWED_CALLBACKS:
                return await handler(event, data)

            if any(cb_data.startswith(p) for p in ALLOWED_PREFIXES):
                return await handler(event, data)

            # Блокируем
            await event.answer(
                "🔒 Для доступа нужна активная подписка.\n"
                "Перейди: Личное → Кошелёк → Купить тариф",
                show_alert=True
            )
            return

        return await handler(event, data)