"""
handlers/group_chat.py  —  ИИ-общение в группах.
Включать в main.py ПОСЛЕ attendance.router
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
        {"$set": {"chat_id": chat_id, "enabled": enabled, "updated_at": datetime.now().isoformat()}},
        upsert=True
    )

async def get_group_laziness(chat_id: int) -> int:
    doc = await group_settings.find_one({"chat_id": chat_id})
    return doc.get("laziness", 60) if doc else 60

# Регистрируем группу при добавлении бота
@router.my_chat_member()
async def on_bot_added(event, bot: Bot):
    try:
        if (event.new_chat_member.status in ("member", "administrator")
                and event.chat.type in ("group", "supergroup")):
            await group_settings.update_one(
                {"chat_id": event.chat.id},
                {"$setOnInsert": {
                    "chat_id": event.chat.id,
                    "chat_title": event.chat.title or "",
                    "enabled": False,
                    "laziness": 60,
                    "added_at": datetime.now().isoformat(),
                }},
                upsert=True
            )
    except Exception as e:
        logger.error(f"[GROUP] my_chat_member: {e}")

YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

SYSTEM = (
    "Ты — ИИ-помощник в студенческой группе, имя Math Tutor Bot. "
    "Отвечай кратко (2-4 предложения), неформально, без LaTeX и HTML. "
    "Отвечай на языке собеседника."
)

async def _ask_ai(text: str, ctx: list) -> str | None:
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs.extend(ctx[-6:])
    msgs.append({"role": "user", "content": text})
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"},
                json={"model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                      "messages": msgs, "temperature": 0.7, "max_tokens": 300}
            ) as r:
                d = await r.json()
                return d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[GROUP AI] {e}")
        return None

_history: dict[int, list] = {}

def _add(chat_id, role, content):
    if chat_id not in _history:
        _history[chat_id] = []
    _history[chat_id].append({"role": role, "content": content})
    if len(_history[chat_id]) > 20:
        _history[chat_id] = _history[chat_id][-20:]

# Фильтр: группы, только текст, исключаем attendance-ссылки
@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def group_message_handler(message: Message, bot: Bot):
    # Пропускаем ссылки посещаемости — их обрабатывает attendance.py
    if message.text and "one.kstu.ru/check-code/" in message.text:
        return

    if not await is_group_chat_enabled(message.chat.id):
        return

    bot_info = await bot.get_me()
    text = message.text.strip()
    should_reply = False

    if f"@{bot_info.username}" in text:
        should_reply = True
        text = text.replace(f"@{bot_info.username}", "").strip()
    elif (message.reply_to_message and message.reply_to_message.from_user
          and message.reply_to_message.from_user.id == bot_info.id):
        should_reply = True
    else:
        laziness = await get_group_laziness(message.chat.id)
        if random.random() < max(0, 100 - laziness) / 100:
            should_reply = True

    name = message.from_user.first_name or "User"
    _add(message.chat.id, "user", f"{name}: {text}")

    if not should_reply:
        return

    ctx = _history.get(message.chat.id, [])[:-1]
    await asyncio.sleep(random.uniform(0.5, 1.5))
    answer = await _ask_ai(text, ctx)
    if not answer:
        return
    _add(message.chat.id, "assistant", answer)
    await message.reply(answer)