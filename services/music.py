"""
handlers/music.py

Функционал:
- Ввод запроса → бот сразу скачивает первый результат
- Кэш file_id в MongoDB (повторный запрос — мгновенно, без скачивания)
- Anti-spam: не чаще 1 запроса в 15 секунд
- Асинхронная загрузка через run_in_executor
- История поиска (последние 10 уникальных запросов)
- Красивое оформление: название, автор, длительность, подпись бота

Зависимости:
    pip install yt-dlp --break-system-packages
    apt-get install ffmpeg -y
"""

import asyncio
import hashlib
import os
import re
import tempfile
import time
from datetime import datetime

from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.exceptions import TelegramBadRequest
from database.stats_models import log_activity
from database.mongo import db


router = Router()


# =========================
# 🗄 Коллекции MongoDB
# =========================
music_cache   = db["music_cache"]    # {cache_key, file_id, title, artist, duration, cached_at}
music_history = db["music_history"]  # {user_id, query, title, ts}

# =========================
# ⚙️ Константы
# =========================
MAX_FILE_MB      = 50
ANTISPAM_SECONDS = 15
HISTORY_LIMIT    = 10

# Антиспам в памяти {user_id: last_request_timestamp}
_last_request: dict[int, float] = {}


# =========================
# FSM
# =========================
class MusicStates(StatesGroup):
    waiting_query = State()


# =========================
# 🎛 Клавиатуры
# =========================
def kb_music_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Найти трек",      callback_data="music_search_start")],
        [InlineKeyboardButton(text="📜 История поиска",  callback_data="music_history")],
        [InlineKeyboardButton(text="⬅️ Назад",           callback_data="focus")],
    ])


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="music_cancel")]
    ])


def kb_after_track() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Ещё трек",      callback_data="music_search_start")],
        [InlineKeyboardButton(text="📜 История",       callback_data="music_history")],
        [InlineKeyboardButton(text="⬅️ В меню фокуса", callback_data="focus")],
    ])


def kb_retry(query: str) -> InlineKeyboardMarkup:
    safe = query[:40]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"music_retry_{safe}")],
        [InlineKeyboardButton(text="🎵 Новый поиск",       callback_data="music_search_start")],
        [InlineKeyboardButton(text="⬅️ В меню",            callback_data="music")],
    ])


def kb_history(items: list) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        query = item.get("query", "")
        label = f"🔁 {query}"[:55]
        safe  = query[:40]
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"music_retry_{safe}")])
    buttons.append([InlineKeyboardButton(text="🗑 Очистить историю", callback_data="music_clear_history")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад",            callback_data="music")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# 🎵 Главное меню
# =========================
@router.callback_query(F.data == "music")
async def music_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text(
            "🎵 <b>Музыка</b>\n\n"
            "Введи название трека или исполнителя — бот скачает и отправит аудиофайл 🎧\n\n"
            "<i>Работает с большинством треков: поп, рок, рэп, классика и т.д.</i>",
            reply_markup=kb_music_main(),
            parse_mode='HTML'
        )
    except TelegramBadRequest:
        pass


# =========================
# 🔍 Запуск поиска
# =========================
@router.callback_query(F.data == "music_search_start")
async def music_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MusicStates.waiting_query)
    try:
        await callback.message.edit_text(
            "🎵 <b>Поиск трека</b>\n\n"
            "Введи название или исполнителя:\n\n"
            "<i>Примеры:\n"
            "• Imagine Dragons Believer\n"
            "• Скриптонит незабудка\n"
            "• MACAN Jet</i>",
            reply_markup=kb_cancel(),
            parse_mode='HTML'
        )
    except TelegramBadRequest:
        pass


# =========================
# 📝 Получение запроса
# =========================
@router.message(MusicStates.waiting_query, F.text)
async def music_got_query(message: Message, state: FSMContext, bot: Bot):
    query   = message.text.strip()
    user_id = message.from_user.id

    if not query:
        await message.answer("❌ Введи название трека:")
        return

    # ── Антиспам ──
    now  = time.time()
    last = _last_request.get(user_id, 0)
    wait = ANTISPAM_SECONDS - (now - last)
    if wait > 0:
        await message.answer(
            f"⏳ Подожди ещё <b>{int(wait) + 1} сек.</b> перед следующим запросом.",
            parse_mode='HTML'
        )
        return

    _last_request[user_id] = now
    await state.clear()

    status = await message.answer(
        f"🔍 Ищу: <i>{query}</i>...",
        parse_mode='HTML'
    )
    await _search_and_download(status, query, user_id, bot)


# =========================
# 🔄 Повтор из истории / retry
# =========================
@router.callback_query(F.data.startswith("music_retry_"))
async def music_retry(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    query   = callback.data.replace("music_retry_", "").strip()
    user_id = callback.from_user.id

    if not query:
        await music_search_start(callback, state)
        return

    now  = time.time()
    last = _last_request.get(user_id, 0)
    wait = ANTISPAM_SECONDS - (now - last)
    if wait > 0:
        await callback.answer(f"⏳ Подожди ещё {int(wait) + 1} сек.", show_alert=True)
        return

    _last_request[user_id] = now
    status = await callback.message.answer(
        f"🔍 Ищу: <i>{query}</i>...",
        parse_mode='HTML'
    )
    await _search_and_download(status, query, user_id, bot)


# =========================
# 📥 Поиск + скачивание
# =========================
async def _search_and_download(status_msg, query: str, user_id: int, bot: Bot):
    # ── Кэш по запросу ──
    query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
    cached = await music_cache.find_one({"query_hash": query_hash})

    if cached and cached.get("file_id"):
        await _safe_edit(status_msg, "⚡ Нашёл в кэше, отправляю...")
        try:
            caption = _build_caption(
                title    = cached["title"],
                artist   = cached.get("artist", ""),
                duration = cached.get("duration"),
                bot_name = (await bot.get_me()).username,
                cached   = True
            )
            await bot.send_audio(
                chat_id   = user_id,
                audio     = cached["file_id"],
                caption   = caption,
                parse_mode= 'HTML',
                title     = cached["title"],
                performer = cached.get("artist", ""),
            )
            await _safe_edit(status_msg, "✅ Готово!", kb_after_track())
            await _give_xp(bot, user_id)
            await _save_history(user_id, query, cached["title"])
            return
        except Exception:
            # file_id устарел — удаляем и скачиваем заново
            await music_cache.delete_one({"query_hash": query_hash})

    # ── Скачиваем ──
    await _safe_edit(status_msg, f"⬇️ <b>Скачиваю...</b>\n<i>{query}</i>")

    try:
        import yt_dlp  # noqa
    except ImportError:
        await _safe_edit(
            status_msg,
            "❌ <b>Модуль yt-dlp не установлен.</b>\n\n"
            "Администратору нужно выполнить:\n"
            "<code>pip install yt-dlp</code>\n"
            "<code>apt-get install ffmpeg -y</code>"
        )
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "format":      "bestaudio/best",
            "outtmpl":     os.path.join(tmpdir, "%(title)s.%(ext)s"),
            "quiet":       True,
            "no_warnings": True,
            "noplaylist":  True,
            "max_filesize": MAX_FILE_MB * 1024 * 1024,
            "default_search": "ytsearch1",
            # ✅ Фикс bot detection
            "extractor_args": {
                "youtube": {
                    "player_client": ["ios", "web"],
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            },
            "socket_timeout": 30,
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }],
        }

        try:
            loop      = asyncio.get_event_loop()
            file_info = await loop.run_in_executor(
                None,
                lambda: _yt_download_sync(query, ydl_opts, tmpdir)
            )
        except Exception as e:
            await _safe_edit(
                status_msg,
                f"❌ <b>Ошибка при загрузке</b>\n\n<code>{str(e)[:150]}</code>",
                kb_retry(query)
            )
            return

        if not file_info or not file_info.get("filepath"):
            await _safe_edit(
                status_msg,
                f"😔 <b>Не удалось найти трек</b>\n\n"
                f"<i>{query}</i>\n\n"
                "Попробуй уточнить запрос:\n"
                "• добавь имя исполнителя\n"
                "• проверь написание",
                kb_retry(query)
            )
            return

        filepath  = file_info["filepath"]
        file_size = os.path.getsize(filepath)

        if file_size > MAX_FILE_MB * 1024 * 1024:
            await _safe_edit(
                status_msg,
                f"❌ <b>Файл слишком большой</b>\n\n"
                f"Размер: {file_size // (1024*1024)} МБ  (лимит {MAX_FILE_MB} МБ)\n"
                "Попробуй найти более короткую версию.",
                kb_retry(query)
            )
            return

        track_title  = file_info.get("title",  query)
        track_artist = file_info.get("artist", "")
        duration     = file_info.get("duration")

        await _safe_edit(status_msg, "📤 Отправляю...")

        bot_username = (await bot.get_me()).username
        caption = _build_caption(
            title    = track_title,
            artist   = track_artist,
            duration = duration,
            bot_name = bot_username,
        )

        safe_name  = _safe_filename(track_title) + ".mp3"
        audio_file = FSInputFile(filepath, filename=safe_name)

        try:
            sent = await bot.send_audio(
                chat_id   = user_id,
                audio     = audio_file,
                caption   = caption,
                parse_mode= 'HTML',
                title     = track_title,
                performer = track_artist,
            )

            # Сохраняем file_id в кэш по query_hash
            fid = sent.audio.file_id if sent.audio else None
            if fid:
                await music_cache.update_one(
                    {"query_hash": query_hash},
                    {"$set": {
                        "query_hash": query_hash,
                        "file_id":    fid,
                        "title":      track_title,
                        "artist":     track_artist,
                        "duration":   duration,
                        "cached_at":  datetime.now().isoformat(),
                    }},
                    upsert=True
                )

            await _safe_edit(status_msg, "✅ <b>Готово!</b> 🎧", kb_after_track())
            await _save_history(user_id, query, track_title)
            await _give_xp(bot, user_id)

        except Exception as e:
            await _safe_edit(
                status_msg,
                f"❌ <b>Ошибка при отправке файла</b>\n\n<code>{str(e)[:100]}</code>",
                kb_retry(query)
            )


# =========================
# 🔧 Синхронная загрузка (для executor)
# =========================
def _yt_download_sync(query: str, opts: dict, tmpdir: str) -> dict | None:
    import yt_dlp

    # Пробуем YouTube
    try:
        result = _try_download(f"ytsearch1:{query}", opts, tmpdir)
        if result:
            return result
    except Exception as e:
        if "Sign in" in str(e) or "bot" in str(e).lower():
            pass  # fallback на SoundCloud
        else:
            raise

    # Fallback — SoundCloud
    try:
        sc_opts = dict(opts)
        sc_opts.pop("extractor_args", None)
        sc_opts.pop("http_headers", None)
        return _try_download(f"scsearch1:{query}", sc_opts, tmpdir)
    except Exception:
        return None


def _try_download(search_query: str, opts: dict, tmpdir: str) -> dict | None:
    import yt_dlp
    result = {}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search_query, download=True)
        if not info:
            return None
        entry = info
        if "entries" in info and info["entries"]:
            entry = info["entries"][0]
        result["title"]    = entry.get("title", "")
        result["artist"]   = (
            entry.get("artist") or entry.get("uploader") or
            entry.get("channel") or ""
        )
        result["duration"] = entry.get("duration")

    for fname in os.listdir(tmpdir):
        if fname.endswith(".mp3"):
            result["filepath"] = os.path.join(tmpdir, fname)
            return result
    for fname in os.listdir(tmpdir):
        if any(fname.endswith(ext) for ext in (".m4a", ".webm", ".ogg", ".opus")):
            result["filepath"] = os.path.join(tmpdir, fname)
            return result
    return None


# =========================
# 📜 История поиска
# =========================
@router.callback_query(F.data == "music_history")
async def music_show_history(callback: CallbackQuery):
    await callback.answer()
    history = await _get_history(callback.from_user.id)

    if not history:
        await _safe_edit(
            callback.message,
            "📜 <b>История поиска пуста</b>\n\n"
            "Найди первый трек — и он появится здесь.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 Найти трек", callback_data="music_search_start")],
                [InlineKeyboardButton(text="⬅️ Назад",      callback_data="music")],
            ])
        )
        return

    await _safe_edit(
        callback.message,
        "📜 <b>История поиска</b>\n\n"
        "Нажми на запрос, чтобы скачать снова:",
        kb_history(history)
    )


@router.callback_query(F.data == "music_clear_history")
async def music_clear_history(callback: CallbackQuery):
    await callback.answer()
    await music_history.delete_many({"user_id": callback.from_user.id})
    await _safe_edit(
        callback.message,
        "🗑 <b>История очищена</b>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Найти трек", callback_data="music_search_start")],
            [InlineKeyboardButton(text="⬅️ Назад",      callback_data="music")],
        ])
    )


# =========================
# ❌ Отмена
# =========================
@router.callback_query(F.data == "music_cancel")
async def music_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _safe_edit(
        callback.message,
        "🎵 <b>Музыка</b>\n\n"
        "Введи название трека или исполнителя — бот скачает и отправит аудиофайл 🎧",
        kb_music_main()
    )


# =========================
# 🔧 Утилиты
# =========================
def _fmt_duration(seconds) -> str:
    try:
        s = int(seconds)
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"
    except Exception:
        return ""


def _safe_filename(title: str) -> str:
    if not title:
        return "track"
    return re.sub(r'[\\/*?:"<>|]', "", title)[:80]


def _build_caption(
    title:    str,
    artist:   str,
    duration,
    bot_name: str = "",
    cached:   bool = False
) -> str:
    lines = []

    # Разделитель сверху
    lines.append("🎵 <b>───── Трек ─────</b>")
    lines.append("")

    lines.append(f"🎼 <b>{title}</b>")

    if artist:
        lines.append(f"👤 {artist}")

    dur = _fmt_duration(duration)
    if dur:
        lines.append(f"⏱ {dur}")

    if cached:
        lines.append("⚡ <i>из кэша</i>")

    lines.append("")
    lines.append("─────────────────")

    if bot_name:
        lines.append(f"📥 <i>Скачано через @{bot_name}</i>")

    return "\n".join(lines)


async def _safe_edit(msg, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest:
        pass


async def _save_history(user_id: int, query: str, title: str):
    """Добавляет запрос в историю, ограничивает HISTORY_LIMIT."""
    await music_history.insert_one({
        "user_id": user_id,
        "query":   query,
        "title":   title,
        "ts":      datetime.now().isoformat(),
    })
    # Удаляем старые записи сверх лимита
    all_docs = await music_history.find(
        {"user_id": user_id}
    ).sort("ts", -1).skip(HISTORY_LIMIT).to_list(length=100)
    if all_docs:
        await music_history.delete_many({"_id": {"$in": [d["_id"] for d in all_docs]}})


async def _get_history(user_id: int) -> list:
    cursor = music_history.find({"user_id": user_id}).sort("ts", -1).limit(HISTORY_LIMIT * 2)
    result, seen = [], set()
    async for doc in cursor:
        q = doc.get("query", "")
        if q not in seen:
            seen.add(q)
            result.append(doc)
        if len(result) >= HISTORY_LIMIT:
            break
    return result


async def _give_xp(bot: Bot, user_id: int):
    try:
        from services.xp import give_xp
        await give_xp(bot, user_id, "music_downloaded")
        await log_activity(user_id, "music")
    except Exception:
        pass