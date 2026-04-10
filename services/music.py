"""
handlers/music.py

Поиск и скачивание музыки.
Использует yt-dlp — умеет скачивать с VK, YouTube, SoundCloud и других источников.

Установка зависимостей:
    pip install yt-dlp --break-system-packages
    apt-get install ffmpeg   # или: pip install ffmpeg-python

Подключить в main.py:
    from handlers import music
    dp.include_router(music.router)
"""

import asyncio
import os
import re
import tempfile

from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.exceptions import TelegramBadRequest

router = Router()

# Максимальный размер файла для отправки в Telegram (50 МБ)
MAX_FILE_MB = 50

# Источники поиска (порядок важен — пробуем сверху вниз)
# yt-dlp поддерживает ytsearch, scsearch и другие
SEARCH_SOURCES = [
    ("ytsearch1", "YouTube"),
    ("scsearch1", "SoundCloud"),
]


# =========================
# FSM
# =========================
class MusicStates(StatesGroup):
    waiting_query = State()   # Ожидание названия трека


# =========================
# Клавиатуры
# =========================
def kb_music_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="music_cancel")]
    ])


def kb_music_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Ещё трек", callback_data="music"),
            InlineKeyboardButton(text="⬅️ В меню",   callback_data="focus"),
        ]
    ])


def kb_music_retry(query: str) -> InlineKeyboardMarkup:
    # query обрезаем для callback_data (макс 64 байта)
    safe_query = query[:40]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"music_retry_{safe_query}")],
        [InlineKeyboardButton(text="🎵 Новый поиск",       callback_data="music")],
        [InlineKeyboardButton(text="⬅️ В меню",            callback_data="focus")],
    ])


# =========================
# 🎵 Вход в раздел музыки
# =========================
@router.callback_query(F.data == "music")
async def music_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MusicStates.waiting_query)
    try:
        await callback.message.edit_text(
            "🎵 <b>Музыка</b>\n\n"
            "Введи название трека или исполнителя:\n\n"
            "<i>Примеры:\n"
            "• Imagine Dragons — Believer\n"
            "• Скриптонит — Незабудка\n"
            "• Coldplay Yellow</i>\n\n"
            "Бот найдёт и отправит тебе аудиофайл 🎧",
            reply_markup=kb_music_cancel(),
            parse_mode='HTML'
        )
    except TelegramBadRequest:
        pass


# =========================
# 🔍 Получение запроса
# =========================
@router.message(MusicStates.waiting_query, F.text)
async def music_search(message: Message, state: FSMContext, bot: Bot):
    query = message.text.strip()
    if not query:
        await message.answer("❌ Введи название трека:")
        return

    await state.clear()
    await _download_and_send(message, query, bot)


# =========================
# 🔄 Повтор из кнопки
# =========================
@router.callback_query(F.data.startswith("music_retry_"))
async def music_retry(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    query = callback.data.replace("music_retry_", "").strip()
    if not query:
        await music_open(callback, state)
        return
    # Отправляем новое сообщение со статусом
    status = await callback.message.answer(
        f"🔍 <b>Ищу:</b> <i>{query}</i>...",
        parse_mode='HTML'
    )
    await _do_download(status, query, bot, callback.from_user.id)


# =========================
# ❌ Отмена
# =========================
@router.callback_query(F.data == "music_cancel")
async def music_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text(
            "🎯 <b>Фокус</b>\nВыбери что хочешь сделать:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎧 Музыка",           callback_data="music")],
                [InlineKeyboardButton(text="🍅 Таймер Помодоро",  callback_data="pomodoro_timer")],
                [InlineKeyboardButton(text="✅ To-Do список",     callback_data="to_do_list")],
                [InlineKeyboardButton(text="⬅️ Назад",            callback_data="back_to_main")],
            ]),
            parse_mode='HTML'
        )
    except TelegramBadRequest:
        pass


# =========================
# 📥 Основная логика скачивания
# =========================
async def _download_and_send(message: Message, query: str, bot: Bot):
    status = await message.answer(
        f"🔍 <b>Ищу:</b> <i>{query}</i>...",
        parse_mode='HTML'
    )
    await _do_download(status, query, bot, message.from_user.id)


async def _do_download(status_msg, query: str, bot: Bot, user_id: int):
    """
    Пытается скачать трек через yt-dlp.
    status_msg — сообщение для обновления статуса.
    """
    try:
        import yt_dlp
    except ImportError:
        await status_msg.edit_text(
            "❌ <b>Модуль yt-dlp не установлен.</b>\n\n"
            "Администратору нужно выполнить:\n"
            "<code>pip install yt-dlp</code>",
            parse_mode='HTML'
        )
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(title)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "max_filesize": MAX_FILE_MB * 1024 * 1024,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        # Пробуем источники по очереди
        downloaded_file = None
        track_title = None
        track_duration = None
        track_artist = None

        for prefix, source_name in SEARCH_SOURCES:
            search_query = f"{prefix}:{query}"
            await _safe_edit(status_msg, f"🔍 Ищу <i>{query}</i> в {source_name}...")

            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    None,
                    lambda sq=search_query: _yt_extract(sq, ydl_opts, tmpdir)
                )

                if info and info.get("filepath"):
                    downloaded_file = info["filepath"]
                    track_title    = info.get("title", query)
                    track_duration = info.get("duration")
                    track_artist   = info.get("uploader") or info.get("artist", "")
                    break

            except Exception as e:
                print(f"[MUSIC] {source_name} failed for '{query}': {e}")
                continue

        if not downloaded_file or not os.path.exists(downloaded_file):
            await status_msg.edit_text(
                f"😔 <b>Трек не найден</b>\n\n"
                f"Не удалось найти: <i>{query}</i>\n\n"
                f"Попробуй:\n"
                f"• Уточнить запрос (исполнитель — название)\n"
                f"• Проверить написание",
                reply_markup=kb_music_retry(query),
                parse_mode='HTML'
            )
            return

        # Проверяем размер
        file_size = os.path.getsize(downloaded_file)
        if file_size > MAX_FILE_MB * 1024 * 1024:
            await status_msg.edit_text(
                f"❌ <b>Файл слишком большой</b>\n\n"
                f"Размер: {file_size // (1024*1024)} МБ (лимит {MAX_FILE_MB} МБ)\n\n"
                f"Попробуй найти более короткую версию трека.",
                reply_markup=kb_music_retry(query),
                parse_mode='HTML'
            )
            return

        await _safe_edit(status_msg, "📤 Отправляю...")

        # Формируем подпись
        duration_str = _fmt_duration(track_duration) if track_duration else ""
        caption = f"🎵 <b>{track_title}</b>"
        if track_artist:
            caption += f"\n👤 {track_artist}"
        if duration_str:
            caption += f"\n⏱ {duration_str}"
        caption += f"\n\n📥 <i>Скачано для @{(await bot.get_me()).username}</i>"

        try:
            audio_file = FSInputFile(downloaded_file, filename=f"{_safe_filename(track_title)}.mp3")
            await bot.send_audio(
                chat_id=user_id,
                audio=audio_file,
                caption=caption,
                parse_mode='HTML',
                title=track_title,
                performer=track_artist or "",
            )
            await status_msg.edit_text(
                f"✅ <b>Готово!</b> Трек отправлен 🎧",
                reply_markup=kb_music_back()
            )

            # Начисляем XP
            try:
                from services.xp import give_xp
                await give_xp(bot, user_id, "music_downloaded")
            except Exception:
                pass

        except Exception as e:
            print(f"[MUSIC] Send error: {e}")
            await status_msg.edit_text(
                "❌ <b>Ошибка при отправке файла.</b>\n\nПопробуй другой трек.",
                reply_markup=kb_music_retry(query),
                parse_mode='HTML'
            )


def _yt_extract(search_query: str, ydl_opts: dict, tmpdir: str) -> dict | None:
    """Синхронная функция для run_in_executor."""
    import yt_dlp

    result = {}
    opts = {**ydl_opts}

    # Хук для получения имени файла после скачивания
    downloaded_files = []

    def progress_hook(d):
        if d["status"] == "finished":
            downloaded_files.append(d["filename"])

    opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(search_query, download=True)

        if not info:
            return None

        # Берём первый результат из поиска
        if "entries" in info:
            entry = info["entries"][0] if info["entries"] else None
        else:
            entry = info

        if not entry:
            return None

        result["title"]    = entry.get("title", "")
        result["duration"] = entry.get("duration")
        result["uploader"] = entry.get("uploader") or entry.get("channel", "")
        result["artist"]   = entry.get("artist", "")

        # Ищем mp3 файл в tmpdir
        for fname in os.listdir(tmpdir):
            if fname.endswith(".mp3"):
                result["filepath"] = os.path.join(tmpdir, fname)
                break

        # Если mp3 не нашли — берём первый попавшийся аудиофайл
        if not result.get("filepath"):
            for fname in os.listdir(tmpdir):
                if any(fname.endswith(ext) for ext in (".webm", ".m4a", ".ogg", ".opus")):
                    result["filepath"] = os.path.join(tmpdir, fname)
                    break

    return result if result.get("filepath") else None


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
    """Убирает спецсимволы из имени файла."""
    if not title:
        return "track"
    return re.sub(r'[\\/*?:"<>|]', "", title)[:80]


async def _safe_edit(msg, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest:
        pass
