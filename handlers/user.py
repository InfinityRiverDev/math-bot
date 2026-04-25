import os
import aiohttp
import asyncio
import io
import time
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

import keyboards.user_kb as kb
from handlers.admin import ADMIN_IDS
from services.calculator import solve_math, solve_from_image
from database.models import register_user
from database.models import get_history, update_history
from services.xp import give_xp
from database.stats_models import log_activity


router = Router()


# FSM — состояния бота
class CalculatorStates(StatesGroup):
    waiting_for_input = State()
    tutor_waiting = State()
    practice_waiting = State()
    art_waiting = State()


# =============================================================
# 🖼 ШАБЛОНЫ ПРЕЗЕНТАЦИЙ
# =============================================================
# Здесь меняй названия, описания и пути к файлам коллажей.
#
# "name"  — отображается пользователю как заголовок шаблона
#           (должно совпадать с текстом кнопки в user_kb.py → presentation)
# "desc"  — короткое описание, которое видит пользователь под фото
# "file"  — путь к файлу коллажа относительно корня проекта
#
# Файлы коллажей положи сюда: media/presentation_templates/
#   collage_1.jpg  ← коллаж из 1.pptx
#   collage_2.jpg  ← коллаж из 2.pptx
#   collage_3.jpg  ← коллаж из 3.pptx
#   collage_4.jpg  ← коллаж из nature__2_.pptx (переименуй файл)
# =============================================================

TEMPLATES = {
    "collage_1": {
        "name": "Шаблон 1 — [название]",       # ← МЕНЯЙ: название шаблона
        "desc": "Описание первого шаблона",      # ← МЕНЯЙ: описание для пользователя
        "file": "media/presentation_templates/collage_1.jpg",  # ← путь к файлу
    },
    "collage_2": {
        "name": "Шаблон 2 — [название]",        # ← МЕНЯЙ: название шаблона
        "desc": "Описание второго шаблона",      # ← МЕНЯЙ: описание для пользователя
        "file": "media/presentation_templates/collage_2.jpg",
    },
    "collage_3": {
        "name": "Шаблон 3 — [название]",        # ← МЕНЯЙ: название шаблона
        "desc": "Описание третьего шаблона",     # ← МЕНЯЙ: описание для пользователя
        "file": "media/presentation_templates/collage_3.jpg",
    },
    "collage_4": {
        "name": "Шаблон 4 — [название]",        # ← МЕНЯЙ: название шаблона
        "desc": "Описание четвёртого шаблона",   # ← МЕНЯЙ: описание для пользователя
        "file": "media/presentation_templates/collage_4.jpg",
    },
}


# ========================
# ИИ-репетитор (меню)
# ========================

@router.callback_query(F.data == 'ai_tutor_menu')
async def cmd_ai_tutor_menu(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            '<b>🎓 ИИ-репетитор</b>\nВыбери что хочешь сделать:',
            reply_markup=kb.ai_tutor_menu,
            parse_mode='HTML'
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data == 'back_to_ai_tutor_menu')
async def cmd_back_to_ai_tutor_menu(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.edit_text(
            '<b>🎓 ИИ-репетитор</b>\nВыбери что хочешь сделать:',
            reply_markup=kb.ai_tutor_menu,
            parse_mode='HTML'
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data == 'practice')
async def cmd_practice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CalculatorStates.practice_waiting)
    await state.update_data(current_task=None, cancelled=False)
    await callback.message.edit_text(
        '✍️ <b>Практика</b>\n\n'
        'Напиши тему — и я дам тебе задачи для тренировки.\n\n'
        'Например: <code>производная</code>, <code>интегралы</code>, <code>пределы</code>\n\n'
        'Для выхода напиши /cancel',
        parse_mode='HTML'
    )

@router.callback_query(F.data == 'ai_additional_functions')
async def cmd_ai_additional_functions(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        'Выберите:',
        reply_markup=kb.ai_additional_functions,
        parse_mode='HTML'
    )


# ========================
# Образование
# ========================

@router.callback_query(F.data == 'education')
async def cmd_education(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>📚 Образование</b>\nВыбери что хочешь сделать:',
        reply_markup=kb.education,
        parse_mode='HTML'
    )


@router.callback_query(F.data == 'lectures')
async def cmd_lectures(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>📖 Лекции</b>\nВыбери что хочешь сделать:',
        reply_markup=kb.lectures,
        parse_mode='HTML'
    )


# ========================
# Услуги
# ========================

@router.callback_query(F.data == 'services')
async def cmd_services(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>Ты попал в раздел Услуги.</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.services,
                                     parse_mode='HTML')


@router.callback_query(F.data == 'backward_to_services')
async def cmd_backward_to_services(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>Ты попал в раздел Услуги.</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.services,
                                     parse_mode='HTML')


@router.callback_query(F.data == 'print')
async def cmd_print(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>Вы можете заказать печать любых файлов, картинок, докладов, рефератов и тд.</b>\n\n'
        '• Цена одной страницы печати - 10₽\n'
        '• Заказ можно будет забрать в институте или в ДАС №6\n\n'
        'Для того чтобы заказать печать обратитесь к менеджеру:',
        reply_markup=kb.print_kb,
        parse_mode='HTML'
    )

@router.callback_query(F.data == 'paid_works')
async def cmd_paid_works(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>Вы можете заказать любую работу из списка:</b>',
        reply_markup=kb.paid_works,
        parse_mode='HTML'
    )

@router.callback_query(F.data == 'backward_to_paid_works')
async def cmd_backward_to_paid_works(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>Вы можете заказать любую работу из списка:</b>',
        reply_markup=kb.paid_works,
        parse_mode='HTML'
    )

@router.callback_query(F.data == 'presentation')
async def cmd_presentation(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>Здесь вы можете заказать презентацию.\n\n</b>'
        '• Цена презентации из 10 слайдов - 250₽\n'
        '• Срок изготовления - 1 день.\n\n'
        'Выберите шаблон вашей презентации:',
        reply_markup=kb.presentation,
        parse_mode='HTML'
    )

@router.callback_query(F.data == 'backward_to_presentation')
async def cmd_backward_to_presentation(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(
        '<b>Здесь вы можете заказать презентацию.\n\n</b>'
        '• Цена презентации из 10 слайдов - 250₽\n'
        '• Срок изготовления - 1 день.\n\n'
        'Выберите шаблон вашей презентации:',
        reply_markup=kb.presentation,
        parse_mode='HTML'
    )

async def _send_template(callback: CallbackQuery, key: str):
    tmpl = TEMPLATES[key]
    await callback.answer()
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer_photo(
        photo=FSInputFile(tmpl["file"]),
        caption=(
            f"🎞️ <b>{tmpl['name']}</b>\n\n"
            f"📌 {tmpl['desc']}\n\n"
            f"💰 <b>Цена:</b> от 250₽ · срок 1 день\n\n"
            f"Нажмите кнопку ниже — откроется чат с менеджером:"
        ),
        reply_markup=kb.get_order_pr_kb(tmpl["name"]),
        parse_mode='HTML'
    )


@router.callback_query(F.data == 'collage_1')
async def cmd_pr_1(callback: CallbackQuery):
    await _send_template(callback, "collage_1")

@router.callback_query(F.data == 'collage_2')
async def cmd_pr_2(callback: CallbackQuery):
    await _send_template(callback, "collage_2")

@router.callback_query(F.data == 'collage_3')
async def cmd_pr_3(callback: CallbackQuery):
    await _send_template(callback, "collage_3")

@router.callback_query(F.data == 'collage_4')
async def cmd_pr_4(callback: CallbackQuery):
    await _send_template(callback, "collage_4")

# ========================
# Личное
# ========================

@router.callback_query(F.data == 'personal')
async def cmd_personal(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>👤 Личное</b>\nВыбери что хочешь сделать:',
        reply_markup=kb.personal,
        parse_mode='HTML'
    )


@router.callback_query(F.data == 'profile')
async def cmd_profile(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>👤 Профиль</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.profile,
                                     parse_mode='HTML')


@router.callback_query(F.data == 'backward_to_profile')
async def cmd_backward_to_profile(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>👤 Профиль</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.profile,
                                     parse_mode='HTML')


@router.callback_query(F.data == 'my_xp')
async def cmd_my_xp(callback: CallbackQuery):
    await callback.answer()
    from database.xp_models import get_xp_profile, get_xp_history
    profile = await get_xp_profile(callback.from_user.id)
    history = await get_xp_history(callback.from_user.id, limit=5)

    history_lines = ""
    if history:
        action_names = {
            "tutor_message": "💬 Вопрос репетитору", "tutor_voice": "🎤 Голосовой вопрос",
            "practice_request": "✍️ Практика", "calc_text": "🧮 Калькулятор",
            "pomodoro_completed": "🍅 Помодоро", "todo_completed": "✅ Задача выполнена",
            "lecture_downloaded": "📖 Лекция", "attendance_marked": "📍 Отметка на паре",
            "music_downloaded": "🎵 Трек", "registration": "🎉 Регистрация",
        }
        history_lines = "\n\n<b>Последние начисления:</b>\n"
        for h in history:
            name = action_names.get(h["action"], h["action"])
            history_lines += f"• {name}: <b>+{h['amount']} XP</b>\n"

    to_next = f"До след. уровня: <b>{profile['xp_to_next']} XP</b>" if not profile["max_level"] else "🌟 Максимальный уровень!"

    await callback.message.edit_text(
        f"⭐ <b>Мои XP</b>\n\n"
        f"🏆 Уровень: {profile['level']}\n"
        f"✨ Всего XP: <b>{profile['xp']}</b>\n"
        f"{profile['bar']}  {to_next}"
        f"{history_lines}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ]),
        parse_mode='HTML'
    )


# ========================
# Расписание
# ========================

@router.callback_query(F.data == 'schedule')
async def cmd_schedule(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>📆 Ваше расписание:</b>',
        reply_markup=kb.schedule,
        parse_mode='HTML'
    )


# ========================
# Фокус
# ========================

@router.callback_query(F.data == 'focus')
async def cmd_focus(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        '<b>🎯 Фокус</b>\nВыбери что хочешь сделать:',
        reply_markup=kb.focus,
        parse_mode='HTML'
    )


# ========================
# Отмена
# ========================
from middlewares.subscription_check import check_sub

@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    if not await check_sub(message.from_user.id, message):
        return

    await state.update_data(cancelled=True)
    await asyncio.sleep(0.1)

    data = await state.get_data()
    task = data.get("current_task")
    if task and not task.done():
        task.cancel()
        await asyncio.sleep(0.1)

    await state.clear()
    await message.answer(
        '⛔ Остановлено.\nВернулся в главное меню 👇',
        reply_markup=kb.get_start_kb(message.from_user.id in ADMIN_IDS)
    )


# ========================
# ИИ-репетитор — вход
# ========================

@router.callback_query(F.data == 'ai-tutor')
async def open_tutor(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CalculatorStates.tutor_waiting)
    await state.update_data(current_task=None, cancelled=False)
    await callback.message.edit_text(
        '🎓 <b>ИИ-репетитор по математике</b>\n\n'
        'Я помогу разобраться с любой математической темой!\n\n'
        '✏️ <b>Текстом</b> — задай вопрос по теме\n'
        '📷 <b>Фото</b> — пришли страницу из учебника\n'
        '🎤 <b>Голосовым</b> — задай вопрос голосом\n'
        '📄 <b>Документом</b> — прикрепи файл с вопросами\n\n'
        'Для выхода напиши /cancel',
        parse_mode='HTML'
    )


# ========================
# ИИ-репетитор — текст
# ========================

@router.message(CalculatorStates.tutor_waiting, F.text)
async def tutor_handle_text(message: Message, state: FSMContext, bot: Bot):
    res_msg = await message.answer("🤔 <b>Думаю...</b>", parse_mode='HTML')
    await state.update_data(cancelled=False)
    history = await get_history(message.from_user.id)

    from services.tutor import ask_tutor, clean_response
    full_text, displayed_text, last_edit_time = "", "", 0

    async def stream_response():
        nonlocal full_text, displayed_text, last_edit_time
        async for chunk in ask_tutor(message.text, history):
            check = await state.get_data()
            if check.get("cancelled"):
                break
            full_text += chunk
            current_clean = clean_response(full_text)
            if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
                try:
                    await res_msg.edit_text(f"{current_clean} ▌", parse_mode='HTML')
                    displayed_text, last_edit_time = current_clean, time.time()
                except:
                    pass
        return full_text

    task = asyncio.create_task(stream_response())
    await state.update_data(current_task=task)

    try:
        await task
        check = await state.get_data()
        if check.get("cancelled"):
            try:
                await res_msg.delete()
            except:
                pass
            return
        final_text = clean_response(full_text)
        if not final_text.strip():
            final_text = "⚠️ Не удалось получить ответ. Попробуйте снова."
        try:
            await res_msg.edit_text(final_text, parse_mode='HTML')
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])

        await log_activity(message.from_user.id, "tutor")

        await give_xp(bot, message.from_user.id, "tutor_message")

        await state.update_data(current_task=None)
    except asyncio.CancelledError:
        try:
            await res_msg.delete()
        except:
            pass


# ========================
# ИИ-репетитор — фото
# ========================

@router.message(CalculatorStates.tutor_waiting, F.photo)
async def tutor_handle_photo(message: Message, state: FSMContext, bot: Bot):
    res_msg = await message.answer("📸 <b>Изучаю фото...</b>", parse_mode='HTML')
    await state.update_data(cancelled=False)

    try:
        photo = message.photo[-1]
        file_in_io = io.BytesIO()
        await bot.download(photo, destination=file_in_io)
        image_bytes = file_in_io.getvalue()

        await res_msg.edit_text("🤔 <b>Думаю над ответом...</b>", parse_mode='HTML')

        data = await state.get_data()
        history = data.get("tutor_history", [])

        from services.tutor import ask_tutor_image, clean_response
        full_text, displayed_text, last_edit_time = "", "", 0

        async def stream_response():
            nonlocal full_text, displayed_text, last_edit_time
            async for chunk in ask_tutor_image(image_bytes, history):
                check = await state.get_data()
                if check.get("cancelled"):
                    break
                full_text += chunk
                current_clean = clean_response(full_text)
                if current_clean != displayed_text and (time.time() - last_edit_time) > 0.7:
                    try:
                        await res_msg.edit_text(f"📷 <b>Разбор фото:</b>\n\n{current_clean} ▌", parse_mode='HTML')
                        displayed_text, last_edit_time = current_clean, time.time()
                    except:
                        pass
            return full_text

        task = asyncio.create_task(stream_response())
        await state.update_data(current_task=task)

        await task
        check = await state.get_data()
        if check.get("cancelled"):
            try:
                await res_msg.delete()
            except:
                pass
            return

        final_text = clean_response(full_text)
        if not final_text.strip():
            final_text = "⚠️ Не удалось получить ответ. Попробуйте снова."
        try:
            await res_msg.edit_text(f"📷 <b>Разбор фото:</b>\n\n{final_text}", parse_mode='HTML')
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        history.append({"role": "user", "content": "[пользователь прислал фото]"})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])
        await state.update_data(current_task=None)

    except asyncio.CancelledError:
        try:
            await res_msg.delete()
        except:
            pass
    except Exception as e:
        await res_msg.edit_text(f"❌ Ошибка при обработке фото: {str(e)}")


# ========================
# ИИ-репетитор — голосовое
# ========================

@router.message(CalculatorStates.tutor_waiting, F.voice)
async def tutor_handle_voice(message: Message, state: FSMContext, bot: Bot):
    res_msg = await message.answer("🎤 <b>Слушаю...</b>", parse_mode='HTML')
    await state.update_data(cancelled=False)

    try:
        voice_buffer = io.BytesIO()
        await bot.download(message.voice, destination=voice_buffer)
        voice_bytes = voice_buffer.getvalue()

        from services.tutor import speech_to_text, ask_tutor, clean_response

        await res_msg.edit_text("🔍 <b>Распознаю речь...</b>", parse_mode='HTML')
        user_text = await speech_to_text(voice_bytes)

        if not user_text:
            await res_msg.edit_text("❌ Не удалось распознать речь. Попробуйте сказать четче.")
            return

        await res_msg.edit_text(
            f"🗣 <i>Вы сказали: \"{user_text}\"</i>\n\n🤔 <b>Думаю...</b>",
            parse_mode='HTML'
        )

        data = await state.get_data()
        history = data.get("tutor_history", [])
        full_text, displayed_text, last_edit_time = "", "", 0

        async def stream_response():
            nonlocal full_text, displayed_text, last_edit_time
            async for chunk in ask_tutor(user_text, history):
                check = await state.get_data()
                if check.get("cancelled"):
                    break
                full_text += chunk
                current_clean = clean_response(full_text)
                if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
                    try:
                        await res_msg.edit_text(
                            f"🗣 <i>\"{user_text}\"</i>\n\n{current_clean} ▌",
                            parse_mode='HTML'
                        )
                        displayed_text, last_edit_time = current_clean, time.time()
                    except:
                        pass
            return full_text

        task = asyncio.create_task(stream_response())
        await state.update_data(current_task=task)

        await task
        check = await state.get_data()
        if check.get("cancelled"):
            try:
                await res_msg.delete()
            except:
                pass
            return

        final_text = clean_response(full_text)
        if not final_text.strip():
            final_text = "⚠️ Не удалось получить ответ. Попробуйте снова."
        try:
            await res_msg.edit_text(f"🗣 <i>\"{user_text}\"</i>\n\n{final_text}", parse_mode='HTML')
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])

        await give_xp(bot, message.from_user.id, "tutor_voice")

        await state.update_data(current_task=None)

    except asyncio.CancelledError:
        try:
            await res_msg.delete()
        except:
            pass
    except Exception as e:
        await res_msg.edit_text(f"❌ Ошибка ГС: {str(e)}")


# ========================
# ИИ-репетитор — документ
# ========================

@router.message(CalculatorStates.tutor_waiting, F.document)
async def tutor_handle_document(message: Message, state: FSMContext, bot: Bot):
    res_msg = await message.answer("📄 <b>Читаю документ...</b>", parse_mode='HTML')
    doc = message.document
    await state.update_data(cancelled=False)

    try:
        file_in_io = io.BytesIO()
        await bot.download(doc, destination=file_in_io)
        file_bytes = file_in_io.getvalue()

        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("cp1251", errors="ignore")

        if not text.strip():
            await res_msg.edit_text("❌ Документ пустой.")
            return

        await res_msg.edit_text("🤔 <b>Анализирую содержимое...</b>", parse_mode='HTML')

        data = await state.get_data()
        history = data.get("tutor_history", [])

        from services.tutor import ask_tutor, clean_response
        full_text, displayed_text, last_edit_time = "", "", 0

        async def stream_response():
            nonlocal full_text, displayed_text, last_edit_time
            async for chunk in ask_tutor(f"Проанализируй этот текст из файла:\n{text[:3000]}", history):
                check = await state.get_data()
                if check.get("cancelled"):
                    break
                full_text += chunk
                current_clean = clean_response(full_text)
                if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
                    try:
                        await res_msg.edit_text(
                            f"📄 <b>Разбор документа:</b>\n\n{current_clean} ▌",
                            parse_mode='HTML'
                        )
                        displayed_text, last_edit_time = current_clean, time.time()
                    except:
                        pass
            return full_text

        task = asyncio.create_task(stream_response())
        await state.update_data(current_task=task)

        await task
        check = await state.get_data()
        if check.get("cancelled"):
            try:
                await res_msg.delete()
            except:
                pass
            return

        final_text = clean_response(full_text)
        if not final_text.strip():
            final_text = "⚠️ Не удалось получить ответ. Попробуйте снова."
        try:
            await res_msg.edit_text(f"📄 <b>Разбор документа:</b>\n\n{final_text}", parse_mode='HTML')
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        history.append({"role": "user", "content": f"Файл: {doc.file_name}"})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])
        await state.update_data(current_task=None)

    except asyncio.CancelledError:
        try:
            await res_msg.delete()
        except:
            pass
    except Exception as e:
        await res_msg.edit_text(f"❌ Ошибка при чтении файла: {str(e)}")


# ========================
# Практика — текст
# ========================

@router.message(CalculatorStates.practice_waiting, F.text)
async def practice_handle_text(message: Message, state: FSMContext, bot: Bot):
    res_msg = await message.answer("✍️ <b>Генерирую задачи...</b>", parse_mode='HTML')
    await state.update_data(cancelled=False)

    from services.tutor import ask_practice, clean_response

    full_text, displayed_text, last_edit_time = "", "", 0

    async def stream_response():
        nonlocal full_text, displayed_text, last_edit_time
        async for chunk in ask_practice(message.text):
            check = await state.get_data()
            if check.get("cancelled"):
                break
            full_text += chunk
            current_clean = clean_response(full_text)
            if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
                try:
                    await res_msg.edit_text(f"{current_clean} ▌", parse_mode='HTML')
                    displayed_text, last_edit_time = current_clean, time.time()
                except:
                    pass
        return full_text

    task = asyncio.create_task(stream_response())
    await state.update_data(current_task=task)

    await log_activity(message.from_user.id, "practice")
    await give_xp(bot, message.from_user.id, "practice_request")

    try:
        await task
        check = await state.get_data()
        if check.get("cancelled"):
            try:
                await res_msg.delete()
            except:
                pass
            return
        final_text = clean_response(full_text)
        if not final_text.strip():
            final_text = "⚠️ Не удалось получить ответ. Попробуйте снова."
        try:
            await res_msg.edit_text(final_text, parse_mode='HTML')
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await state.update_data(current_task=None)
    except asyncio.CancelledError:
        try:
            await res_msg.delete()
        except:
            pass