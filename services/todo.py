"""
handlers/todo.py

Полноценный To-Do список.

Подключить в main.py:
    from handlers import todo
    dp.include_router(todo.router)

Callback-данные не используют FSM для навигации —
вся логика через callback_data, FSM только для ввода текста.
"""

import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.exceptions import TelegramBadRequest
from database.stats_models import log_activity
from database.todo_models import (
    get_todos, add_todo, toggle_todo, cycle_priority,
    edit_todo_text, delete_todo, clear_done, get_stats, get_todo
)
from services.xp import give_xp

router = Router()

PAGE_SIZE = 5  # задач на странице

PRIORITY_EMOJI = {1: "🟢", 2: "🟡", 3: "🔴"}
PRIORITY_LABEL = {1: "низкий", 2: "средний", 3: "высокий"}
FILTER_LABEL   = {"all": "Все", "active": "Активные", "done": "Выполненные"}


# =========================
# FSM
# =========================
class TodoStates(StatesGroup):
    adding_text      = State()   # Ввод текста новой задачи
    adding_deadline  = State()   # Ввод дедлайна (опционально)
    editing_text     = State()   # Редактирование текста задачи


# =========================
# 🔧 Вспомогательные функции
# =========================

async def safe_edit(msg, text: str, markup: InlineKeyboardMarkup = None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def fmt_deadline(deadline: str | None) -> str:
    if not deadline:
        return ""
    try:
        dt = datetime.fromisoformat(deadline)
        now = datetime.now()
        diff = (dt.date() - now.date()).days
        if diff < 0:
            return f" <b>⚠️ просрочено</b> ({dt.strftime('%d.%m')})"
        elif diff == 0:
            return f" <b>🔥 сегодня</b>"
        elif diff == 1:
            return f" ⏰ завтра"
        else:
            return f" 📅 {dt.strftime('%d.%m.%Y')}"
    except Exception:
        return ""


def parse_deadline_input(text: str) -> str | None:
    """
    Принимает: ДД.ММ, ДД.ММ.ГГГГ или '-' (пропустить).
    Возвращает ISO-строку или None.
    """
    text = text.strip()
    if text in ("-", "нет", "skip", "пропустить", "0"):
        return None
    try:
        if re.match(r"^\d{2}\.\d{2}$", text):
            dt = datetime.strptime(f"{text}.{datetime.now().year}", "%d.%m.%Y")
        elif re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
            dt = datetime.strptime(text, "%d.%m.%Y")
        else:
            return "error"
        return dt.isoformat()
    except ValueError:
        return "error"


# =========================
# 🎛 Клавиатуры
# =========================

def kb_todo_list(
    items: list,
    page: int,
    total: int,
    filter_mode: str,
    stats: dict
) -> InlineKeyboardMarkup:
    """Клавиатура главного списка задач."""
    buttons = []

    # Переключатель фильтра
    filters = ["all", "active", "done"]
    filter_row = []
    for f in filters:
        label = f"• {FILTER_LABEL[f]} •" if f == filter_mode else FILTER_LABEL[f]
        filter_row.append(InlineKeyboardButton(
            text=label,
            callback_data=f"todo_filter_{f}"
        ))
    buttons.append(filter_row)

    # Задачи
    start = page * PAGE_SIZE
    page_items = items[start:start + PAGE_SIZE]

    for item in page_items:
        done_mark = "✅" if item["done"] else "⬜"
        priority  = PRIORITY_EMOJI[item.get("priority", 2)]
        deadline  = fmt_deadline(item.get("deadline"))

        # Обрезаем длинный текст
        text = item["text"]
        if len(text) > 28:
            text = text[:25] + "..."

        row_label = f"{done_mark} {priority} {text}"
        buttons.append([
            InlineKeyboardButton(
                text=row_label,
                callback_data=f"todo_open_{item['_id']}"
            )
        ])

    # Пагинация
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"todo_page_{filter_mode}_{page - 1}"))
        nav.append(InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="todo_noop"
        ))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"todo_page_{filter_mode}_{page + 1}"))
        buttons.append(nav)

    # Нижние действия
    buttons.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="todo_add"),
        InlineKeyboardButton(text="🧹 Очистить ✅", callback_data="todo_clear_done"),
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="focus")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kb_todo_item(todo_id: str, done: bool, filter_mode: str, page: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки задачи."""
    done_btn = "✅ Готово" if not done else "↩️ Вернуть"
    back_cb  = f"todo_page_{filter_mode}_{page}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=done_btn,        callback_data=f"todo_toggle_{todo_id}_{filter_mode}_{page}"),
            InlineKeyboardButton(text="🔄 Приоритет",  callback_data=f"todo_priority_{todo_id}_{filter_mode}_{page}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить",   callback_data=f"todo_edit_{todo_id}_{filter_mode}_{page}"),
            InlineKeyboardButton(text="🗑 Удалить",    callback_data=f"todo_delete_{todo_id}_{filter_mode}_{page}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ К списку",   callback_data=back_cb),
        ]
    ])


def kb_deadline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Сегодня",  callback_data="todo_dl_today"),
            InlineKeyboardButton(text="📅 Завтра",   callback_data="todo_dl_tomorrow"),
        ],
        [
            InlineKeyboardButton(text="➡️ Без срока", callback_data="todo_dl_skip"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена",    callback_data="todo_cancel_add"),
        ]
    ])


def kb_priority_select() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Низкий",   callback_data="todo_pr_1"),
            InlineKeyboardButton(text="🟡 Средний",  callback_data="todo_pr_2"),
            InlineKeyboardButton(text="🔴 Высокий",  callback_data="todo_pr_3"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена",   callback_data="todo_cancel_add"),
        ]
    ])


# =========================
# 📋 Построение текста списка
# =========================

def build_list_text(stats: dict, filter_mode: str, total: int) -> str:
    done  = stats["done"]
    total_all = stats["total"]

    if total_all == 0:
        progress = "Список пуст"
    else:
        bar_len  = 10
        filled   = int(bar_len * done / total_all) if total_all else 0
        bar      = "🟦" * filled + "⬜" * (bar_len - filled)
        progress = f"{bar}  {done}/{total_all}"

    filter_str = FILTER_LABEL[filter_mode]
    shown_str  = f"Показаны: <b>{filter_str}</b> ({total})"

    return (
        f"✅ <b>To-Do список</b>\n\n"
        f"📊 Прогресс: {progress}\n"
        f"{shown_str}\n\n"
        f"Нажми на задачу для управления:"
    )


# =========================
# 🏠 Вход в To-Do
# =========================

@router.callback_query(F.data == "to_do_list")
async def todo_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _show_list(callback, "all", 0)


async def _show_list(callback: CallbackQuery, filter_mode: str, page: int):
    user_id = callback.from_user.id
    items   = await get_todos(user_id, filter_mode)
    stats   = await get_stats(user_id)

    text   = build_list_text(stats, filter_mode, len(items))
    markup = kb_todo_list(items, page, len(items), filter_mode, stats)

    await safe_edit(callback.message, text, markup)


# =========================
# 🔃 Фильтры
# =========================

@router.callback_query(F.data.startswith("todo_filter_"))
async def todo_filter(callback: CallbackQuery):
    await callback.answer()
    filter_mode = callback.data.replace("todo_filter_", "")
    await _show_list(callback, filter_mode, 0)


# =========================
# 📄 Пагинация
# =========================

@router.callback_query(F.data.startswith("todo_page_"))
async def todo_page(callback: CallbackQuery):
    await callback.answer()
    # формат: todo_page_{filter}_{page}
    parts       = callback.data.split("_")
    filter_mode = parts[2]
    page        = int(parts[3])
    await _show_list(callback, filter_mode, page)


@router.callback_query(F.data == "todo_noop")
async def todo_noop(callback: CallbackQuery):
    await callback.answer()


# =========================
# 📌 Открыть карточку задачи
# =========================

@router.callback_query(F.data.startswith("todo_open_"))
async def todo_open_item(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    todo_id = callback.data.replace("todo_open_", "")

    # Сохраняем контекст (откуда пришли) в state
    data = await state.get_data()
    filter_mode = data.get("todo_filter", "all")
    page        = data.get("todo_page", 0)

    item = await get_todo(todo_id)
    if not item:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return

    await state.update_data(todo_filter=filter_mode, todo_page=page)
    await safe_edit(
        callback.message,
        _item_text(item),
        kb_todo_item(todo_id, item["done"], filter_mode, page)
    )


def _item_text(item: dict) -> str:
    priority = PRIORITY_EMOJI[item.get("priority", 2)]
    status   = "✅ Выполнено" if item["done"] else "⏳ В процессе"
    deadline = fmt_deadline(item.get("deadline"))
    created  = item.get("created_at", "")[:10]

    deadline_line = f"\n📅 <b>Срок:</b>{deadline}" if item.get("deadline") else ""
    done_at_line  = ""
    if item.get("done") and item.get("done_at"):
        done_at_line = f"\n✔️ <b>Выполнено:</b> {item['done_at'][:10]}"

    return (
        f"{priority} <b>{item['text']}</b>\n\n"
        f"🏷 <b>Статус:</b> {status}\n"
        f"⚡ <b>Приоритет:</b> {PRIORITY_LABEL[item.get('priority', 2)]}"
        f"{deadline_line}"
        f"{done_at_line}\n"
        f"🗓 <b>Создано:</b> {created}"
    )


# =========================
# ✅ Переключить выполнение
# =========================

@router.callback_query(F.data.startswith("todo_toggle_"))
async def todo_toggle(callback: CallbackQuery):
    await callback.answer()
    # формат: todo_toggle_{id}_{filter}_{page}
    parts       = callback.data.split("_")
    todo_id     = parts[2]
    filter_mode = parts[3]
    page        = int(parts[4])

    await toggle_todo(todo_id)
    if item["done"]:
        await give_xp(callback.bot, callback.from_user.id, "todo_completed")
    item = await get_todo(todo_id)
    if not item:
        await _show_list(callback, filter_mode, page)
        return

    await safe_edit(
        callback.message,
        _item_text(item),
        kb_todo_item(todo_id, item["done"], filter_mode, page)
    )


# =========================
# 🔄 Сменить приоритет
# =========================

@router.callback_query(F.data.startswith("todo_priority_"))
async def todo_change_priority(callback: CallbackQuery):
    await callback.answer()
    parts       = callback.data.split("_")
    todo_id     = parts[2]
    filter_mode = parts[3]
    page        = int(parts[4])

    await cycle_priority(todo_id)
    item = await get_todo(todo_id)
    if not item:
        return

    await safe_edit(
        callback.message,
        _item_text(item),
        kb_todo_item(todo_id, item["done"], filter_mode, page)
    )


# =========================
# ✏️ Редактировать задачу
# =========================

@router.callback_query(F.data.startswith("todo_edit_"))
async def todo_edit_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts       = callback.data.split("_")
    todo_id     = parts[2]
    filter_mode = parts[3]
    page        = int(parts[4])

    item = await get_todo(todo_id)
    if not item:
        return

    await state.set_state(TodoStates.editing_text)
    await state.update_data(
        editing_todo_id=todo_id,
        todo_filter=filter_mode,
        todo_page=page
    )

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"todo_open_{todo_id}")]
    ])
    await safe_edit(
        callback.message,
        f"✏️ <b>Редактирование задачи</b>\n\n"
        f"Текущий текст:\n<i>{item['text']}</i>\n\n"
        f"Введи новый текст:",
        cancel_kb
    )


@router.message(TodoStates.editing_text, F.text)
async def todo_edit_done(message: Message, state: FSMContext):
    new_text = message.text.strip()
    if not new_text:
        await message.answer("❌ Текст не может быть пустым.")
        return

    data    = await state.get_data()
    todo_id = data.get("editing_todo_id")

    await edit_todo_text(todo_id, new_text)
    await state.clear()

    item = await get_todo(todo_id)
    filter_mode = data.get("todo_filter", "all")
    page        = data.get("todo_page", 0)

    await message.answer(
        f"✅ Задача обновлена!\n\n" + _item_text(item),
        reply_markup=kb_todo_item(todo_id, item["done"], filter_mode, page),
        parse_mode='HTML'
    )


# =========================
# 🗑 Удалить задачу
# =========================

@router.callback_query(F.data.startswith("todo_delete_"))
async def todo_delete(callback: CallbackQuery):
    await callback.answer("🗑 Удалено")
    parts       = callback.data.split("_")
    todo_id     = parts[2]
    filter_mode = parts[3]
    page        = int(parts[4])

    await delete_todo(todo_id)
    await _show_list(callback, filter_mode, max(0, page))


# =========================
# 🧹 Очистить выполненные
# =========================

@router.callback_query(F.data == "todo_clear_done")
async def todo_clear(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    filter_mode = data.get("todo_filter", "all")

    stats = await get_stats(callback.from_user.id)
    if stats["done"] == 0:
        await callback.answer("✅ Нет выполненных задач для очистки", show_alert=True)
        return

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🗑 Удалить ({stats['done']})", callback_data="todo_clear_confirm"),
            InlineKeyboardButton(text="❌ Отмена",                     callback_data=f"todo_filter_{filter_mode}"),
        ]
    ])
    await safe_edit(
        callback.message,
        f"🧹 <b>Очистить выполненные?</b>\n\n"
        f"Будет удалено задач: <b>{stats['done']}</b>\n"
        f"Это действие необратимо.",
        confirm_kb
    )


@router.callback_query(F.data == "todo_clear_confirm")
async def todo_clear_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer("🧹 Готово")
    await clear_done(callback.from_user.id)
    await _show_list(callback, "all", 0)


# =========================
# ➕ Добавить задачу — шаг 1: текст
# =========================

@router.callback_query(F.data == "todo_add")
async def todo_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TodoStates.adding_text)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="todo_cancel_add")]
    ])
    await safe_edit(
        callback.message,
        "➕ <b>Новая задача</b>\n\n"
        "Введи текст задачи:",
        cancel_kb
    )


@router.message(TodoStates.adding_text, F.text)
async def todo_add_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("❌ Введи текст задачи:")
        return

    if len(text) > 500:
        await message.answer("❌ Слишком длинный текст (максимум 500 символов).")
        return

    await state.update_data(new_todo_text=text)
    await state.set_state(TodoStates.adding_deadline)

    await message.answer(
        f"📝 <b>Задача:</b> <i>{text}</i>\n\n"
        "📅 <b>Укажи срок выполнения</b> или нажми «Без срока»:\n\n"
        "<i>Формат: 25.01 или 25.01.2026</i>",
        reply_markup=kb_deadline(),
        parse_mode='HTML'
    )


# =========================
# ➕ Шаг 2: дедлайн (кнопки)
# =========================

@router.callback_query(F.data == "todo_dl_today")
async def todo_dl_today(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    deadline = datetime.now().replace(hour=23, minute=59).isoformat()
    await state.update_data(new_todo_deadline=deadline)
    await _ask_priority(callback, state)


@router.callback_query(F.data == "todo_dl_tomorrow")
async def todo_dl_tomorrow(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    from datetime import timedelta
    deadline = (datetime.now() + timedelta(days=1)).replace(hour=23, minute=59).isoformat()
    await state.update_data(new_todo_deadline=deadline)
    await _ask_priority(callback, state)


@router.callback_query(F.data == "todo_dl_skip")
async def todo_dl_skip(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(new_todo_deadline=None)
    await _ask_priority(callback, state)


# =========================
# ➕ Шаг 2: дедлайн (текстовый ввод)
# =========================

@router.message(TodoStates.adding_deadline, F.text)
async def todo_add_deadline_text(message: Message, state: FSMContext):
    result = parse_deadline_input(message.text)
    if result == "error":
        await message.answer(
            "❌ Неверный формат. Введи дату как <code>25.01</code> или <code>25.01.2026</code>\n"
            "Или нажми кнопку «Без срока».",
            parse_mode='HTML'
        )
        return

    await state.update_data(new_todo_deadline=result)

    # Имитируем callback для перехода к приоритету
    # Отправляем отдельным сообщением
    data = await state.get_data()
    await message.answer(
        "⚡ <b>Выбери приоритет задачи:</b>",
        reply_markup=kb_priority_select(),
        parse_mode='HTML'
    )


async def _ask_priority(callback: CallbackQuery, state: FSMContext):
    await safe_edit(
        callback.message,
        "⚡ <b>Выбери приоритет задачи:</b>",
        kb_priority_select()
    )


# =========================
# ➕ Шаг 3: приоритет → сохранить
# =========================

@router.callback_query(F.data.in_({"todo_pr_1", "todo_pr_2", "todo_pr_3"}))
async def todo_add_priority(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    priority = int(callback.data[-1])

    data     = await state.get_data()
    text     = data.get("new_todo_text", "")
    deadline = data.get("new_todo_deadline")

    if not text:
        await callback.answer("❌ Что-то пошло не так. Начни заново.", show_alert=True)
        await state.clear()
        return

    todo_id = await add_todo(
        user_id=callback.from_user.id,
        text=text,
        priority=priority,
        deadline=deadline
    )

    await log_activity(callback.from_user.id, "todo")

    await give_xp(callback.bot, callback.from_user.id, "todo_added")
    await state.clear()

    item = await get_todo(todo_id)
    await safe_edit(
        callback.message,
        f"✅ <b>Задача добавлена!</b>\n\n" + _item_text(item),
        kb_todo_item(todo_id, False, "all", 0)
    )


# =========================
# ❌ Отмена добавления
# =========================

@router.callback_query(F.data == "todo_cancel_add")
async def todo_cancel_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await _show_list(callback, "all", 0)
