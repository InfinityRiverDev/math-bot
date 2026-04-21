"""
handlers/group_chat.py  - ИИ-общение в группах.
"""
import os, re, random, asyncio, aiohttp, logging
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

GROUP_SYSTEM_PROMPT = """Ты - дружелюбный ИИ-помощник в студенческой группе. Имя - Math Tutor Bot.
Правила:
1. Отвечай кратко (2-4 предложения)
2. Будь неформальным - ты среди студентов
3. Если математика - помогай
4. Если болтают - поддержи разговор
5. Никакого LaTeX, HTML или markdown - только обычный текст
6. Отвечай на языке собеседника"""

YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

async def ask_ai_group(text: str, context: list = None) -> str:
    messages = [{"role": "system", "content": GROUP_SYSTEM_PROMPT}]
    if context:
        messages.extend(context[-6:])
    messages.append({"role": "user", "content": text})
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"},
                json={"model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                      "messages": messages, "temperature": 0.7, "max_tokens": 300}
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[GROUP AI] {e}")
        return None

_chat_history: dict = {}

def _add_history(chat_id: int, role: str, text: str):
    if chat_id not in _chat_history:
        _chat_history[chat_id] = []
    _chat_history[chat_id].append({"role": role, "content": text})
    if len(_chat_history[chat_id]) > 20:
        _chat_history[chat_id] = _chat_history[chat_id][-20:]

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: Message, bot: Bot):
    if message.text and "one.kstu.ru/check-code/" in message.text:
        return
    if not await is_group_chat_enabled(message.chat.id):
        return
    if not message.text:
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
    _add_history(message.chat.id, "user", f"{name}: {text}")

    if not should_reply:
        return

    context = _chat_history.get(message.chat.id, [])[:-1]
    await asyncio.sleep(random.uniform(0.5, 1.5))
    answer = await ask_ai_group(text, context)
    if not answer:
        return
    _add_history(message.chat.id, "assistant", answer)
    await message.reply(answer)