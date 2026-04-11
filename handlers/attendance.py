"""
handlers/attendance.py
Автоматическая отметка посещаемости.

Мониторит сообщения в группах/каналах.
Если видит ссылку https://one.kstu.ru/check-code/<uuid> —
получает токен каждого пользователя и отмечает их всех.
"""

import re
import asyncio
import aiohttp
from aiogram import Router, Bot, F
from aiogram.types import Message

from database.models import get_all_users, get_user_profile
from handlers.registration import check_knrtu_auth
from database.stats_models import log_activity
from handlers.admin import ADMIN_IDS

router = Router()

# Уже обработанные коды (в памяти, сбрасываются при перезапуске)
processed_codes: set[str] = set()

ATTENDANCE_URL = "https://rest.kstu.ru/restapi/workbook/check-visit/"
CODE_REGEX = re.compile(r"https://one\.kstu\.ru/check-code/([a-z0-9\-]+)", re.IGNORECASE)


async def mark_user(session: aiohttp.ClientSession, token: str, code: str) -> bool:
    """Отмечает одного пользователя. Возвращает True при успехе."""
    try:
        async with session.post(
            ATTENDANCE_URL,
            headers={
                "accept": "*/*",
                "accept-language": "ru,en;q=0.9",
                "authorization": f"Token {token}",
                "content-type": "application/json",
                "Referer": "https://one.kstu.ru/"
            },
            json={"curlid_code": code}
        ) as resp:
            data = await resp.json()
            print(f"ATTENDANCE for code {code}:", data)
            return data.get("status") is True
    except Exception as e:
        print(f"ATTENDANCE ERROR: {e}")
        return False


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def watch_attendance_link(message: Message, bot: Bot):
    """Обработчик сообщений в группах — ищет ссылки на отметку."""
    if not message.text:
        return

    match = CODE_REGEX.search(message.text)
    if not match:
        return

    code = match.group(1)

    if code in processed_codes:
        print(f"Code {code} already processed, skipping.")
        return

    processed_codes.add(code)
    print(f"Found attendance code: {code}")

    # Получаем всех зарегистрированных пользователей
    user_ids = await get_all_users()

    success_users = []
    fail_users = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for user_id in user_ids:
            tasks.append(_process_one_user(session, bot, user_id, code, success_users, fail_users))

        await asyncio.gather(*tasks)

    # Отчёт администраторам
    report_lines = [
        f"📊 <b>Отчёт по отметке</b>\n",
        f"🔑 Код: <code>{code}</code>\n",
        f"✅ Успешно: <b>{len(success_users)}</b>",
        f"❌ Ошибки: <b>{len(fail_users)}</b>",
        f"👥 Всего: <b>{len(user_ids)}</b>",
    ]

    if fail_users:
        report_lines.append("\n<b>Не отмечены:</b>")
        for entry in fail_users[:20]:  # ограничиваем длину
            report_lines.append(f"• {entry['login']} (id: {entry['user_id']}) — {entry['reason']}")

    report = "\n".join(report_lines)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, report, parse_mode='HTML')
        except Exception as e:
            print(f"Can't send report to admin {admin_id}: {e}")


async def _process_one_user(
    session: aiohttp.ClientSession,
    bot: Bot,
    user_id: int,
    code: str,
    success_users: list,
    fail_users: list
):
    """Получает токен пользователя и отмечает его."""
    profile = await get_user_profile(user_id)
    if not profile:
        fail_users.append({"user_id": user_id, "login": "?", "reason": "профиль не найден"})
        return

    login = profile.get("knrtu_login")
    raw_password = profile.get("knrtu_password_raw")

    if not login or not raw_password:
        fail_users.append({
            "user_id": user_id,
            "login": login or "?",
            "reason": "нет логина/пароля"
        })
        return

    # Получаем свежий токен
    token = await check_knrtu_auth(login, raw_password)
    if not token:
        fail_users.append({
            "user_id": user_id,
            "login": login,
            "reason": "не удалось получить токен"
        })
        return

    success = await mark_user(session, token, code)

    if success:
        success_users.append({"user_id": user_id, "login": login})

        await log_activity(user_id, "attendance")

        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Вы отмечены на лекции!</b>\n\n"
                f"🔑 Код: <code>{code}</code>",
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        fail_users.append({
            "user_id": user_id,
            "login": login,
            "reason": "API вернул статус false"
        })