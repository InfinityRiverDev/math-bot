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
        reply_markup=kb.print,
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

@router.callback_query(F.data == 'pr_1')
async def cmd_pr_1(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer_photo(photo=FSInputFile('media/presentation_templates/pr_1.jpg'),
                                        caption='📊 <b>Шаблон:</b> шаблон 1\n'
                                                '📌 <b>Описание:</b> Чистый и аккуратный стиль, идеально для учебы и защиты проектов\n'
                                                '💰 <b>Цена:</b> 250₽\n\n'
                                                'Для заказа нажмите кнопку ниже:',
                                        reply_markup=kb.order_pr_1)


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


# @router.callback_query(F.data == 'music')
# async def cmd_music(callback: CallbackQuery):
#     await callback.answer("🚧 Функция 'Музыка' в разработке!", show_alert=True)



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

### Калькулятор

# # ========================
# # Калькулятор — вход
# # ========================
#
# @router.callback_query(F.data == 'calculator')
# async def open_calculator(callback: CallbackQuery, state: FSMContext):
#     await callback.answer()
#     await state.set_state(CalculatorStates.waiting_for_input)
#     await callback.message.edit_text(
#         '🧮 <b>Умный калькулятор</b>\n\n'
#         'Отправь мне задачу любым удобным способом:\n\n'
#         '✏️ <b>Текстом</b> — например: <code>2^10 + корень из 144</code>\n'
#         '📷 <b>Фото</b> — сфотографируй задачу из учебника\n'
#         '🎤 <b>Голосовым</b> — продиктуй задачу\n'
#         '📄 <b>Документом</b> — прикрепи файл с задачами\n\n'
#         'Для выхода напиши /cancel',
#         parse_mode='HTML'
#     )
#
#
# # ========================
# # Калькулятор — текст
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.text)
# async def handle_text(message: Message, state: FSMContext):
#     thinking_msg = await message.answer('🤔 Решаю задачу...')
#     task = asyncio.create_task(solve_math(message.text))
#     await state.update_data(current_task=task, cancelled=False)
#     try:
#         result = await task
#         await thinking_msg.delete()
#         await message.answer(f"\n{result}", parse_mode='HTML')
#         log_activity()
#     except asyncio.CancelledError:
#         try:
#             await thinking_msg.delete()
#         except:
#             pass
#
#
# # ========================
# # Калькулятор — фото
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.photo)
# async def handle_photo(message: Message, bot: Bot, state: FSMContext):
#     thinking_msg = await message.answer('📷 Распознаю текст на фото...')
#     photo = message.photo[-1]
#     file_in_io = io.BytesIO()
#     await bot.download(photo, destination=file_in_io)
#     image_bytes = file_in_io.getvalue()
#     await thinking_msg.edit_text('🤔 Решаю задачу...')
#     task = asyncio.create_task(solve_from_image(image_bytes))
#     await state.update_data(current_task=task, cancelled=False)
#     try:
#         result = await task
#         await thinking_msg.delete()
#         await message.answer(f"\n{result}", parse_mode='HTML')
#     except asyncio.CancelledError:
#         try:
#             await thinking_msg.delete()
#         except:
#             pass
#
#
# # ========================
# # Калькулятор — голосовое
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.voice)
# async def handle_voice(message: Message, bot: Bot, state: FSMContext):
#     thinking_msg = await message.answer('🎤 Распознаю голосовое сообщение...')
#     voice_buffer = io.BytesIO()
#     await bot.download(message.voice, destination=voice_buffer)
#     audio_bytes = voice_buffer.getvalue()
#
#     api_key = os.getenv("YANDEX_API_KEY")
#     folder_id = os.getenv("YANDEX_FOLDER_ID")
#
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                 "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
#                 headers={"Authorization": f"Api-Key {api_key}"},
#                 params={"lang": "ru-RU", "format": "oggopus", "folderId": folder_id},
#                 data=audio_bytes
#             ) as resp:
#                 data = await resp.json()
#                 recognized_text = data.get("result", "")
#     except Exception:
#         recognized_text = ""
#
#     if not recognized_text:
#         await thinking_msg.delete()
#         await message.answer('❌ Не удалось распознать голосовое сообщение. Попробуй написать задачу текстом.')
#         return
#
#     await thinking_msg.edit_text(f'🤔 Решаю: <i>{recognized_text}</i>...', parse_mode='HTML')
#     task = asyncio.create_task(solve_math(recognized_text))
#     await state.update_data(current_task=task, cancelled=False)
#     try:
#         result = await task
#         await thinking_msg.delete()
#         await message.answer(f'🎤 <b>Распознано:</b> <i>{recognized_text}</i>\n\n{result}', parse_mode='HTML')
#     except asyncio.CancelledError:
#         try:
#             await thinking_msg.delete()
#         except:
#             pass
#
#
# # ========================
# # Калькулятор — документ
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.document)
# async def handle_document(message: Message, bot: Bot, state: FSMContext):
#     doc = message.document
#     mime = doc.mime_type or ""
#
#     if "text" not in mime and "pdf" not in mime:
#         await message.answer(
#             '❌ Поддерживаются только текстовые файлы (.txt).\n'
#             'Для PDF — сфотографируй страницу и пришли как фото.'
#         )
#         return
#
#     thinking_msg = await message.answer('📄 Читаю документ...')
#     file_in_io = io.BytesIO()
#     await bot.download(doc, destination=file_in_io)
#     file_bytes = file_in_io.getvalue()
#
#     try:
#         text = file_bytes.decode("utf-8")
#     except UnicodeDecodeError:
#         text = file_bytes.decode("cp1251", errors="ignore")
#
#     if not text.strip():
#         await thinking_msg.delete()
#         await message.answer('❌ Документ пустой или не удалось прочитать.')
#         return
#
#     await thinking_msg.edit_text('🤔 Решаю задачи из документа...')
#     task = asyncio.create_task(solve_math(f"Задачи из документа:\n{text[:3000]}"))
#     await state.update_data(current_task=task, cancelled=False)
#     try:
#         result = await task
#         await thinking_msg.delete()
#         await message.answer(f"\n{result}", parse_mode='HTML')
#     except asyncio.CancelledError:
#         try:
#             await thinking_msg.delete()
#         except:
#             pass


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

    # ✅ ask_practice — отдельная функция с PRACTICE_PROMPT, без конфликта system-сообщений
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