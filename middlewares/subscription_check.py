"""
middlewares/subscription_check.py

Middleware — проверяет активную подписку.
Без подписки доступны ТОЛЬКО: Услуги, Кошелёк, Профиль, Регистрация.
Администраторы из ADMIN_IDS — всегда без ограничений.
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message

from database.billing_models import has_active_subscription
from database.models import is_registered
from database.models import is_banned, get_user_full
from handlers.admin import ADMIN_IDS


# Callback-данные, разрешённые без подписки
ALLOWED_CALLBACKS = {
    # Навигация
    "back_to_main",
    "personal",
    "profile",
    "user_data",
    "backward_to_profile",
    "profile_view",
    "profile_delete",
    "profile_delete_confirm",
    # Услуги (доступны всем)
    "services",
    "backward_to_services",
    "print",
    "paid_works",
    "backward_to_paid_works",
    "presentation",
    "backward_to_presentation",
    "pr_1", "pr_2", "pr_3", "pr_4", "pr_5",
    # Кошелёк и оплата — ВСЕГДА разрешены
    "wallet_view",
    "wallet_topup",
    "wallet_buy_plan",
    "wallet_withdraw",
    # Заглушка
    "noop",
    "trial_activate"
}

# Префиксы callback, разрешённые без подписки
ALLOWED_PREFIXES = (
    "buy_plan_",
    "confirm_plan_",
    "enter_promo_",
    "order_pr_",
    "reg_",
    "policy_",
    "check_ok_",
    "check_edit_",
)

# Команды, всегда разрешённые
ALLOWED_COMMANDS = {"/start", "/cancel", "/help", "/wallet"}

LOCKED_MESSAGE = (
    "🔒 <b>Доступ ограничен</b>\n\n"
    "Для использования этой функции необходима активная подписка.\n\n"
    "Перейди в раздел <b>Кошелёк</b>, пополни баланс и активируй тариф.\n\n"
    "/wallet — открыть кошелёк"
)


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None

        if isinstance(event, (CallbackQuery, Message)):
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        # Администраторы — полный доступ без ограничений
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        # Незарегистрированные — пускаем (registration сам разберётся)
        registered = await is_registered(user_id)
        if not registered:
            return await handler(event, data)

        # 🔴 БАН — САМЫЙ ВАЖНЫЙ БЛОК
        if await is_banned(user_id):
            if isinstance(event, Message):
                await event.answer("🚫 <b>Вы заблокированы</b>", parse_mode='HTML')
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Вы заблокированы", show_alert=True)
            return

        # # 🔴 Проверка бана
        # if await is_banned(user_id):
        #     user = await get_user_full(user_id)
        #     reason = user.get("ban_reason")
        #
        #     text = "🚫 <b>Вы заблокированы в боте</b>"
        #
        #     if reason:
        #         text += f"\n\n📝 Причина: <i>{reason}</i>"
        #
        #     if isinstance(event, Message):
        #         await event.answer(text, parse_mode='HTML')
        #     elif isinstance(event, CallbackQuery):
        #         await event.answer("🚫 Вы заблокированы", show_alert=True)
        #
        #     return

        # Проверка подписки
        has_sub = await has_active_subscription(user_id)
        if has_sub:
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            if event.data == "trial_activate":
                return await handler(event, data)

        # ─── Нет подписки ───

        if isinstance(event, Message):
            text = (event.text or "").strip()

            # Разрешаем команды
            if any(text.startswith(cmd) for cmd in ALLOWED_COMMANDS):
                return await handler(event, data)

            # Разрешаем ввод данных в активном FSM-состоянии
            state = data.get("state")
            if state:
                current = await state.get_state()
                if current:
                    return await handler(event, data)

            # Блокируем всё остальное
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
                "🔒 Нужна активная подписка.\n"
                "Перейди: Кошелёк → Купить тариф",
                show_alert=True
            )
            return

        return await handler(event, data)



# =======================================================================================================
### Функция, которую можно вставить в любом месте бота и при любом действии для проверки наличия подписки
# =======================================================================================================

async def check_sub(user_id, message):
    from database.billing_models import has_active_subscription
    if not await has_active_subscription(user_id):
        await message.answer("❌ <b>Сначала оплатите подписку</b>", parse_mode='HTML')
        return False
    return True

# Вставлять этот код в нужном месте:
# if not await check_sub(message.from_user.id, message):
#     return

# =======================================================================================================