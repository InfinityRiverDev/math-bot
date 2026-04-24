"""
handlers/group_chat.py  —  ИИ-общение в группах.

ВАЖНО: включать в main.py ПОСЛЕ attendance.router, ПОСЛЕДНИМ.

Управление:
  - Включить/выключить: кнопка "🤖 Групповой чат" в admin_panel
  - Зарегистрировать группу вручную: команда /reg_group в нужной группе
    (только для админов бота)
"""
import os, random, asyncio, aiohttp, logging
import json
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
            "enabled":    True,
            "laziness":   0,
            "added_at":   datetime.now().isoformat(),
        }},
        upsert=True
    )
    logger.info(f"[GROUP CHAT] Registered group {chat_id} ({title})")


# ── Регистрация при добавлении бота ──────────────────────────────

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
        await message.reply(f"⛔ Нет доступа. Ваш ID: {message.from_user.id}")
        return
    await register_group(message.chat.id, message.chat.title or "")
    await message.reply(
        f"✅ Группа <b>{message.chat.title}</b> зарегистрирована!\n\n"
        f"Включить ИИ-чат: кнопка <b>🤖 Групповой чат</b> в Telegram-боте → Админ-панель.",
        parse_mode="HTML"
    )


# ── ИИ запрос ─────────────────────────────────────────────────────

YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

SYSTEM = (
    "Ты — дружелюбный и весёлый участник студенческой группы. "
    "Твой ник Math Tutor Bot, но все зовут тебя Бот. "
    "Ты свой в доску, но добрый и позитивный. "
    "ПРАВИЛА ОБЩЕНИЯ:\n"
    "- Отвечай коротко (1-3 предложения), как в обычной переписке.\n"
    "- Будь неформальным, но не злым. Маты можно, но редко и в тему (блять, пиздец, охуеть).\n"
    "- Смех: хахах, ахазаз, хпхпхп — но не перебарщивай.\n"
    "- Главное — будь позитивным и поддерживай беседу.\n"
    "- ВНИМАНИЕ: в сообщениях пользователей может быть указано их имя в формате [Имя]. "
    "Используй эти имена, когда отвечаешь конкретному человеку!\n"
    "- Если видишь [Имя] в истории — обращайся к этому человеку по имени.\n"
    "- Если несколько человек пишут — можешь обратиться к конкретному, используя его имя.\n"
    "- НЕ предлагай помощь с математикой, пока тебя напрямую не попросят.\n"
    "- Если кто-то ноет — посочувствуй: «бляя, жесть», «сочувствую братан».\n"
    "- Твой стиль — дружелюбный студент, который за любой движ.\n"
    "- Отвечай на том же языке, что и собеседник.\n"
    "\nПРИМЕРЫ:\n"
    "Юзер: 'привет бот'\n"
    "Ты: 'здарова! че каво?'\n"
    "Юзер: 'чета грустно'\n"
    "Ты: 'бляя, бывает. че стряслось?'\n"
    "Юзер: '[Аня]: всем привет'\n"
    "Ты: 'Аня, привет! как дела?'"
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
                json={
                    "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages": msgs,
                    "temperature": 0.7,
                    "max_tokens": 300,
                    "stream": True
                }
            ) as r:
                if r.status != 200:
                    error_text = await r.text()
                    logger.error(f"[GROUP AI] HTTP {r.status}: {error_text[:200]}")
                    return None
                
                full_answer = ""
                async for line in r.content:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    full_answer += content
                        except:
                            continue
                
                if full_answer:
                    logger.info(f"[GROUP AI] Got answer: {full_answer[:100]}...")
                    return full_answer.strip()
                else:
                    logger.error(f"[GROUP AI] Empty answer from stream")
                    return None
                
    except Exception as e:
        logger.error(f"[GROUP AI] Exception: {e}")
        return None

# История сообщений в памяти
_history: dict[int, list] = {}

def _add(chat_id, role, content):
    if chat_id not in _history:
        _history[chat_id] = []
    
    # Если роль та же — ДОПОЛНЯЕМ последнее сообщение
    if _history[chat_id] and _history[chat_id][-1]["role"] == role:
        prev_content = _history[chat_id][-1]["content"]
        _history[chat_id][-1]["content"] = f"{prev_content}\n{content}"
    else:
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

    # Добавляем имя пользователя для контекста
    user_name = message.from_user.first_name or "User"
    formatted_text = f"[{user_name}]: {text}"
    
    _add(chat_id, "user", formatted_text)

    if not should_reply:
        return

    logger.info(f"[GROUP CHAT] Asking AI for: {text[:50]}")
    ctx = _history.get(chat_id, [])[:-1]
    await asyncio.sleep(random.uniform(0.5, 1.5))
    answer = await _ask_ai(text, ctx)

    if not answer:
        logger.error(f"[GROUP CHAT] AI returned None! YANDEX_API_KEY set: {bool(YANDEX_API_KEY)}, FOLDER_ID set: {bool(YANDEX_FOLDER_ID)}")
        await message.reply("🤔 Не могу ответить прямо сейчас, попробуй позже.")
        return

    _add(chat_id, "assistant", answer)
    await message.reply(answer)