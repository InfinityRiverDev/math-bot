"""
handlers/group_chat.py  —  ИИ-общение в группах.

ВАЖНО: включать в main.py ПОСЛЕ attendance.router, ПОСЛЕДНИМ.

Управление:
  - Включить/выключить: кнопка "🤖 Групповой чат" в admin_panel
  - Зарегистрировать группу вручную: команда /reg_group в нужной группе
    (только для админов бота)
"""
import os, random, asyncio, aiohttp, logging
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from database.mongo import db

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
group_settings = db["group_chat_settings"]

ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
try:
    BOT_ADMIN_IDS = set(map(int, ADMIN_IDS_RAW.split(",")))
except Exception:
    BOT_ADMIN_IDS = set()


# ── Вспомогательные функции ───────────────────────────────────────

async def is_group_chat_enabled(chat_id: int) -> bool:
    doc = await group_settings.find_one({"chat_id": chat_id})
    return bool(doc.get("enabled", False)) if doc else False

async def set_group_chat_enabled(chat_id: int, enabled: bool):
    await group_settings.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id, "enabled": enabled, "updated_at": datetime.now().isoformat()}},
        upsert=True
    )

async def get_group_laziness(chat_id: int) -> int:
    doc = await group_settings.find_one({"chat_id": chat_id})
    return int(doc.get("laziness", 60)) if doc else 60

async def register_group(chat_id: int, title: str = ""):
    """Регистрирует группу в БД (если ещё нет)."""
    await group_settings.update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": {
            "chat_id":    chat_id,
            "chat_title": title,
            "enabled":    False,  # выключен по умолчанию
            "laziness":   60,
            "added_at":   datetime.now().isoformat(),
        }},
        upsert=True
    )
    logger.info(f"[GROUP CHAT] Registered group {chat_id} ({title})")


# ── Регистрация при добавлении бота ──────────────────────────────

# ✅ my_chat_member — срабатывает когда бота добавляют/удаляют
@router.my_chat_member()
async def on_bot_status_change(event: ChatMemberUpdated, bot: Bot):
    """Регистрируем группу когда бота добавляют."""
    try:
        new_status = event.new_chat_member.status
        chat       = event.chat
        if (new_status in ("member", "administrator")
                and chat.type in ("group", "supergroup")):
            await register_group(chat.id, chat.title or "")
            logger.info(f"[GROUP CHAT] Auto-registered: {chat.id} ({chat.title})")
    except Exception as e:
        logger.error(f"[GROUP CHAT] my_chat_member error: {e}")


@router.message(Command("reg_group"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_reg_group(message: Message):
    if message.from_user.id not in BOT_ADMIN_IDS:
        # ✅ Теперь отвечаем вместо тихого игнора — для диагностики
        await message.reply(f"⛔ Нет доступа. Ваш ID: {message.from_user.id}")
        return
    await register_group(message.chat.id, message.chat.title or "")
    await message.reply(
        f"✅ Группа <b>{message.chat.title}</b> зарегистрирована!\n\n"
        f"Включить ИИ-чат: кнопка <b>🤖 Групповой чат</b> в Telegram-боте → Админ-панель.",
        parse_mode="HTML"
    )

# ── Ручная регистрация командой /reg_group ────────────────────────

# ── ИИ запрос ─────────────────────────────────────────────────────

YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

SYSTEM = (
    "Ты — дружелюбный ИИ-помощник в студенческой группе. Имя — Math Tutor Bot. "
    "Правила: отвечай кратко (2-4 предложения), неформально, без LaTeX и HTML. "
    "Отвечай на языке собеседника (русский или английский). "
    "Если вопрос про математику — помогай. Если болтают — поддержи разговор."
)

async def _ask_ai(text: str, ctx: list) -> str | None:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        logger.error(f"[GROUP AI] YANDEX_API_KEY или YANDEX_FOLDER_ID не заданы!")
        return None
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
                logger.info(f"[GROUP AI] response status={r.status} body={str(d)[:200]}")
                return d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[GROUP AI] Exception: {e}")
        return None

# История сообщений в памяти
_history: dict[int, list] = {}

def _add(chat_id, role, content):
    if chat_id not in _history:
        _history[chat_id] = []
    _history[chat_id].append({"role": role, "content": content})
    if len(_history[chat_id]) > 20:
        _history[chat_id] = _history[chat_id][-20:]


# ── Обработчик сообщений ──────────────────────────────────────────

@router.message(F.text)
async def group_message_handler(message: Message, bot: Bot):
    if "one.kstu.ru/check-code/" in (message.text or ""):
        return
    if (message.text or "").startswith("/"):
        return

    chat_id = message.chat.id
    doc = await group_settings.find_one({"chat_id": chat_id})
    if not doc:
        await register_group(chat_id, message.chat.title or "")
        return

    if not doc.get("enabled", False):
        logger.warning(f"[GROUP CHAT] {chat_id} — disabled, skipping")
        return

    bot_info = await bot.get_me()
    text = message.text.strip()
    should_reply = False

    if bot_info.username and f"@{bot_info.username}" in text:
        should_reply = True
        text = text.replace(f"@{bot_info.username}", "").strip()
    elif (message.reply_to_message
          and message.reply_to_message.from_user
          and message.reply_to_message.from_user.id == bot_info.id):
        should_reply = True
    else:
        laziness = doc.get("laziness", 60)
        roll = random.random()
        threshold = max(0, 100 - laziness) / 100
        logger.info(f"[GROUP CHAT] roll={roll:.2f} threshold={threshold:.2f} should_reply={roll < threshold}")
        if roll < threshold:
            should_reply = True

    name = message.from_user.first_name or "User"
    _add(chat_id, "user", f"{name}: {text}")

    if not should_reply:
        return

    logger.info(f"[GROUP CHAT] Asking AI for: {text[:50]}")
    ctx = _history.get(chat_id, [])[:-1]
    await asyncio.sleep(random.uniform(0.5, 1.5))
    answer = await _ask_ai(text, ctx)

    # ← НОВОЕ: fallback если AI не ответил
    if not answer:
        logger.error(f"[GROUP CHAT] AI returned None! YANDEX_API_KEY set: {bool(YANDEX_API_KEY)}, FOLDER_ID set: {bool(YANDEX_FOLDER_ID)}")
        await message.reply("🤔 Не могу ответить прямо сейчас, попробуй позже.")
        return

    _add(chat_id, "assistant", answer)
    await message.reply(answer)