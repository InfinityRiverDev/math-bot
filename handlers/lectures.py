"""
handlers/lectures.py
Лекции — админ добавляет предметы и PDF, пользователи просматривают.
"""

import os
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from database.lectures_models import (
    get_all_subjects, add_subject,
    get_lectures_by_subject, add_lecture,
    delete_subject, delete_lecture
)
from database.stats_models import log_activity
from handlers.admin import ADMIN_IDS

router = Router()


# =========================
# FSM для добавления лекций
# =========================
class LectureAdminStates(StatesGroup):
    waiting_subject_name = State()    # Ввод названия предмета
    waiting_lecture_title = State()   # Ввод названия лекции
    waiting_lecture_file = State()    # Загрузка PDF


# =========================
# Клавиатуры
# =========================
async def subjects_kb_user() -> InlineKeyboardMarkup:
    subjects = await get_all_subjects()
    buttons = []
    for subj in subjects:
        buttons.append([InlineKeyboardButton(
            text=f"📘 {subj['name']}",
            callback_data=f"lect_subj_{subj['_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="education")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def subjects_kb_admin() -> InlineKeyboardMarkup:
    subjects = await get_all_subjects()
    buttons = []
    for subj in subjects:
        buttons.append([
            InlineKeyboardButton(text=f"📘 {subj['name']}", callback_data=f"admin_lect_subj_{subj['_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_del_subj_{subj['_id']}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить предмет", callback_data="admin_add_subject")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def lectures_kb_user(subject_id: str) -> InlineKeyboardMarkup:
    lectures = await get_lectures_by_subject(subject_id)
    buttons = []
    for lec in lectures:
        buttons.append([InlineKeyboardButton(
            text=f"📄 {lec['title']}",
            callback_data=f"lect_get_{lec['_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ К предметам", callback_data="pdf-lectures")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def lectures_kb_admin(subject_id: str) -> InlineKeyboardMarkup:
    lectures = await get_lectures_by_subject(subject_id)
    buttons = []
    for lec in lectures:
        buttons.append([
            InlineKeyboardButton(text=f"📄 {lec['title']}", callback_data=f"lect_get_{lec['_id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_del_lect_{lec['_id']}")
        ])
    buttons.append([InlineKeyboardButton(
        text="➕ Добавить лекцию",
        callback_data=f"admin_add_lect_{subject_id}"
    )])
    buttons.append([InlineKeyboardButton(text="⬅️ К предметам", callback_data="admin_add_lecture")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# USER: Список предметов
# =========================
@router.callback_query(F.data == "pdf-lectures")
async def user_subjects_list(callback: CallbackQuery):
    await callback.answer()
    kb = await subjects_kb_user()
    subjects = await get_all_subjects()

    if not subjects:
        await callback.message.edit_text(
            "📭 Лекции пока не добавлены.\nОбратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="education")]
            ])
        )
        return

    await callback.message.edit_text(
        "📚 <b>Выберите предмет:</b>",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# USER: Список лекций по предмету
# =========================
@router.callback_query(F.data.startswith("lect_subj_"))
async def user_lectures_list(callback: CallbackQuery):
    await callback.answer()
    subject_id = callback.data.replace("lect_subj_", "")

    subjects = await get_all_subjects()
    subject = next((s for s in subjects if str(s["_id"]) == subject_id), None)
    subject_name = subject["name"] if subject else "Предмет"

    lectures = await get_lectures_by_subject(subject_id)
    kb = await lectures_kb_user(subject_id)

    if not lectures:
        await callback.message.edit_text(
            f"📘 <b>{subject_name}</b>\n\n📭 Лекций по этому предмету пока нет.",
            reply_markup=kb,
            parse_mode='HTML'
        )
        return

    await callback.message.edit_text(
        f"📘 <b>{subject_name}</b>\n\nВыберите лекцию:",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# USER: Скачать лекцию (PDF)
# =========================
@router.callback_query(F.data.startswith("lect_get_"))
async def user_get_lecture(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    from database.lectures_models import get_lecture_by_id
    lecture_id = callback.data.replace("lect_get_", "")
    lecture = await get_lecture_by_id(lecture_id)

    if not lecture:
        await callback.answer("❌ Лекция не найдена.", show_alert=True)
        return

    file_id = lecture.get("file_id")
    title = lecture.get("title", "Лекция")

    try:
        await bot.send_document(
            callback.from_user.id,
            document=file_id,
            caption=f"📄 <b>{title}</b>",
            parse_mode='HTML'
        )
        log_activity()
        await callback.answer("✅ Лекция отправлена!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# =========================
# ADMIN: Список предметов
# =========================
@router.callback_query(F.data == "admin_add_lecture", F.from_user.id.in_(ADMIN_IDS))
async def admin_subjects_list(callback: CallbackQuery):
    await callback.answer()
    kb = await subjects_kb_admin()
    await callback.message.edit_text(
        "⚙️ <b>Управление лекциями</b>\n\nВыберите предмет или добавьте новый:",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# ADMIN: Добавить предмет — ввод названия
# =========================
@router.callback_query(F.data == "admin_add_subject", F.from_user.id.in_(ADMIN_IDS))
async def admin_add_subject_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(LectureAdminStates.waiting_subject_name)
    await callback.message.edit_text(
        "📘 Введите <b>название предмета</b>:\n\n<i>Например: Математический анализ</i>",
        parse_mode='HTML'
    )


@router.message(LectureAdminStates.waiting_subject_name, F.from_user.id.in_(ADMIN_IDS))
async def admin_add_subject_done(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Слишком короткое название. Введите снова:")
        return

    await add_subject(name)
    await state.clear()

    kb = await subjects_kb_admin()
    await message.answer(
        f"✅ Предмет <b>{name}</b> добавлен!\n\nВыберите предмет для управления лекциями:",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# ADMIN: Удалить предмет
# =========================
@router.callback_query(F.data.startswith("admin_del_subj_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_delete_subject(callback: CallbackQuery):
    subject_id = callback.data.replace("admin_del_subj_", "")
    await delete_subject(subject_id)
    await callback.answer("🗑 Предмет удалён")

    kb = await subjects_kb_admin()
    await callback.message.edit_text(
        "⚙️ <b>Управление лекциями</b>\n\nВыберите предмет или добавьте новый:",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# ADMIN: Список лекций по предмету
# =========================
@router.callback_query(F.data.startswith("admin_lect_subj_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_lectures_list(callback: CallbackQuery):
    await callback.answer()
    subject_id = callback.data.replace("admin_lect_subj_", "")

    subjects = await get_all_subjects()
    subject = next((s for s in subjects if str(s["_id"]) == subject_id), None)
    subject_name = subject["name"] if subject else "Предмет"

    kb = await lectures_kb_admin(subject_id)
    await callback.message.edit_text(
        f"📘 <b>{subject_name}</b>\n\nЛекции:",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# ADMIN: Начать добавление лекции
# =========================
@router.callback_query(F.data.startswith("admin_add_lect_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_add_lecture_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    subject_id = callback.data.replace("admin_add_lect_", "")
    await state.update_data(subject_id=subject_id)
    await state.set_state(LectureAdminStates.waiting_lecture_title)

    await callback.message.edit_text(
        "📝 Введите <b>название лекции</b>:\n\n<i>Например: Лекция 1. Пределы</i>",
        parse_mode='HTML'
    )


@router.message(LectureAdminStates.waiting_lecture_title, F.from_user.id.in_(ADMIN_IDS))
async def admin_add_lecture_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("❌ Слишком короткое название. Введите снова:")
        return

    await state.update_data(lecture_title=title)
    await state.set_state(LectureAdminStates.waiting_lecture_file)
    await message.answer(
        f"✅ Название: <b>{title}</b>\n\n"
        "📎 Теперь отправьте <b>PDF-файл</b> лекции:",
        parse_mode='HTML'
    )


@router.message(LectureAdminStates.waiting_lecture_file, F.document, F.from_user.id.in_(ADMIN_IDS))
async def admin_add_lecture_file(message: Message, state: FSMContext):
    doc = message.document
    if not doc.mime_type or "pdf" not in doc.mime_type.lower():
        await message.answer("❌ Пожалуйста, отправьте файл в формате <b>PDF</b>.", parse_mode='HTML')
        return

    data = await state.get_data()
    subject_id = data.get("subject_id")
    title = data.get("lecture_title")
    file_id = doc.file_id

    await add_lecture(subject_id=subject_id, title=title, file_id=file_id)
    await state.clear()

    kb = await lectures_kb_admin(subject_id)
    await message.answer(
        f"✅ Лекция <b>{title}</b> добавлена!",
        reply_markup=kb,
        parse_mode='HTML'
    )


# =========================
# ADMIN: Удалить лекцию
# =========================
@router.callback_query(F.data.startswith("admin_del_lect_"), F.from_user.id.in_(ADMIN_IDS))
async def admin_delete_lecture(callback: CallbackQuery):
    lecture_id = callback.data.replace("admin_del_lect_", "")

    from database.lectures_models import get_lecture_by_id
    lecture = await get_lecture_by_id(lecture_id)
    subject_id = lecture.get("subject_id") if lecture else None

    await delete_lecture(lecture_id)
    await callback.answer("🗑 Лекция удалена")

    if subject_id:
        kb = await lectures_kb_admin(str(subject_id))
        subjects = await get_all_subjects()
        subject = next((s for s in subjects if str(s["_id"]) == str(subject_id)), None)
        subject_name = subject["name"] if subject else "Предмет"
        await callback.message.edit_text(
            f"📘 <b>{subject_name}</b>\n\nЛекции:",
            reply_markup=kb,
            parse_mode='HTML'
        )