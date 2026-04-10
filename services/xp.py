"""
services/xp.py

Утилита для начисления XP из любого хэндлера.
Импортируй и вызывай: await give_xp(bot, user_id, "action_name")

Если пользователь повысил уровень — бот тихо пришлёт ему уведомление.
"""

from aiogram import Bot
from database.xp_models import award_xp


async def give_xp(bot: Bot, user_id: int, action: str):
    """
    Начисляет XP и при повышении уровня отправляет уведомление.
    Никогда не бросает исключений — безопасно вызывать из любого места.
    """
    try:
        result = await award_xp(user_id, action)
        if result and result.get("leveled_up"):
            level   = result["new_level"]
            xp      = result["xp"]
            to_next = result["xp_to_next"]

            next_text = (
                f"До следующего уровня: <b>{to_next} XP</b>"
                if to_next else "Ты достиг максимального уровня! 🌟"
            )

            await bot.send_message(
                user_id,
                f"🎉 <b>Новый уровень!</b>\n\n"
                f"Ты стал: {level}\n"
                f"Всего XP: <b>{xp}</b>\n\n"
                f"{next_text}",
                parse_mode='HTML'
            )
    except Exception as e:
        print(f"[XP] Error for user {user_id}, action {action}: {e}")
