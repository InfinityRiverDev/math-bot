"""
handlers/group_chat.py  —  ИИ-общение в группах.

Включать в main.py СТРОГО ПОСЛЕ attendance.router
Бот НЕ отвечает если:
  - режим выключен для этой группы (по умолчанию ВЫКЛЮЧЕН)
  - сообщение содержит ссылку посещаемости one.kstu.ru
  - сообщение начинается с / (команда)
  - сообщение от другого бота
"""
import os, random, asyncio, aiohttp, logging
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message
from database.mongo import db

logger = logging.getLogger(__name__)
router = Router()
group_settings = db["group_chat_settings"]


async def is_group_chat_enabled(chat_id: int) -> bool:
    doc = await group_settings.find_one({"chat_id": chat_id})
    return doc.get("enabled", False) if doc else False


async def set_group_chat_enabled(chat_id: int, enabled: bool):
    await group_settings.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "chat_id":    chat_id,
            "enabled":    enabled,
            "updated_at": datetime.now().isoformat()
        }},
        upsert=True
    )


async def get_group_laziness(chat_id: int) -> int:
    """Лень 0–100. При лени=60 бот отвечает с вероятностью ~40%."""
    doc = await group_settings.find_one({"chat_id": chat_id})
    return doc.get("laziness", 60) if doc else 60


@router.my_chat_member()
async def on_bot_added(event, bot: Bot):
    """При добавлении бота в группу — создаём запись (выключен по умолчанию)."""
    try:
        if (event.new_chat_member.status in ("member", "administrator")
                and event.chat.type in ("group", "supergroup")):
            await group_settings.update_one(
                {"chat_id": event.chat.id},
                {"$setOnInsert": {
                    "chat_id":    event.chat.id,
                    "chat_title": event.chat.title or "",
                    "enabled":    False,   # по умолчанию выключен!
                    "laziness":   60,
                    "added_at":   datetime.now().isoformat(),
                }},
                upsert=True
            )
            logger.info(f"[GROUP] Добавлен в {event.chat.id} ({event.chat.title}) — режим ВЫКЛЮЧЕН")
    except Exception as e:
        logger.error(f"[GROUP] my_chat_member error: {e}")


YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

SYSTEM = (
    "Ты — дружелюбный ИИ-помощник в студенческой группе. Имя — Math Tutor Bot.\n"
    "Отвечай кратко (2–4 предложения), неформально, без LaTeX и HTML.\n"
    "Отвечай на языке собеседника."
)

_cache: dict[int, list] = {}


def _add_ctx(chat_id: int, role: str, content: str):
    if chat_id not in _cache:
        _cache[chat_id] = []
    _cache[chat_id].append({"role": role, "content": content})
    if len(_cache[chat_id]) > 20:
        _cache[chat_id] = _cache[chat_id][-20:]


async def _ask_ai(text: str, ctx: list) -> str | None:
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs.extend(ctx[-6:])
    msgs.append({"role": "user", "content": text})
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages":    msgs,
                    "temperature": 0.7,
                    "max_tokens":  300,
                }
            ) as r:
                d = await r.json()
                return d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[GROUP AI] {e}")
        return None


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def group_message_handler(message: Message, bot: Bot):
    text = message.text or ""

    # Строго игнорируем:
    if "one.kstu.ru/check-code/" in text:  # attendance обработает
        return
    if text.startswith("/"):               # команды боту
        return
    if message.from_user and message.from_user.is_bot:  # другие боты
        return

    # Проверяем включён ли режим
    if not await is_group_chat_enabled(message.chat.id):
        return

    bot_info     = await bot.get_me()
    should_reply = False
    reply_text   = text

    # 1. Прямое упоминание @бота
    if f"@{bot_info.username}" in text:
        should_reply = True
        reply_text   = text.replace(f"@{bot_info.username}", "").strip()

    # 2. Реплай на сообщение бота
    elif (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot_info.id
    ):
        should_reply = True

    # 3. Случайный ответ по вероятности
    else:
        laziness = await get_group_laziness(message.chat.id)
        prob = max(0, 100 - laziness) / 100
        if random.random() < prob:
            should_reply = True

    name = message.from_user.first_name if message.from_user else "User"
    _add_ctx(message.chat.id, "user", f"{name}: {reply_text}")

    if not should_reply:
        return

    ctx = _cache.get(message.chat.id, [])[:-1]

    await asyncio.sleep(random.uniform(0.5, 1.5))
    answer = await _ask_ai(reply_text, ctx)
    if not answer:
        return

    _add_ctx(message.chat.id, "assistant", answer)
    await message.reply(answer)