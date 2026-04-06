import os
import aiohttp
import asyncio
import io
import time
from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import keyboards.user_kb as kb
from handlers.admin import ADMIN_IDS
from services.calculator import solve_math, solve_from_image
from database.models import register_user
from database.models import get_history, update_history

router = Router()


# FSM — состояния бота
class CalculatorStates(StatesGroup):
    waiting_for_input = State()
    tutor_waiting = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"

    # ✅ РЕГИСТРАЦИЯ В MONGO
    await register_user(user_id, username)

    is_admin = user_id in ADMIN_IDS

    await message.answer(
        '<b>Привет! Я математический бот 🤖</b>\nВыбери что хочешь сделать:',
        reply_markup=kb.get_start_kb(is_admin),
        parse_mode='HTML'
    )


# ========================
# ИИ
# ========================

@router.callback_query(F.data == 'ai')
async def cmd_ai(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>Ты попал в раздел ИИ.</b>\nВыбери что хочешь сделать:',
                            reply_markup=kb.ai,
                            parse_mode='HTML')


# ========================
# Лекции
# ========================

# @router.callback_query(F.data == 'lectures')
# async def cmd_lectures(callback: CallbackQuery):
#     await callback.answer()
#     await callback.message.edit_text('<b>Ты попал в раздел Лекции.</b>\nВыбери что хочешь сделать:',
#                                      reply_markup=kb.lectures,
#                                      parse_mode='HTML')


# ========================
# Услуги
# ========================

@router.callback_query(F.data == 'services')
async def cmd_services(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>Ты попал в раздел Услуги.</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.services,
                                     parse_mode='HTML')


# ========================
# Профиль
# ========================

@router.callback_query(F.data == 'profile')
async def cmd_profile(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('<b>Ты попал в раздел Профиль.</b>\nВыбери что хочешь сделать:',
                                     reply_markup=kb.profile,
                                     parse_mode='HTML')


# ========================
# Поддержка
# ========================
#
# @router.callback_query(F.data == 'profile')
# async def cmd_profile(callback: CallbackQuery):
#     await callback.answer()


# ========================
# Отмена
# ========================

@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.update_data(cancelled=True)
    await asyncio.sleep(0.1)

    data = await state.get_data()
    task = data.get("current_task")
    if task and not task.done():
        task.cancel()
        await asyncio.sleep(0.1)

    await state.clear()
    await message.answer(
        f'⛔ Остановлено.\nВернулся в главное меню 👇',
        reply_markup=kb.get_start_kb(message.from_user.id in ADMIN_IDS)
    )


# ========================
# Калькулятор — вход
# ========================

@router.callback_query(F.data == 'calculator')
async def open_calculator(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(CalculatorStates.waiting_for_input)
    await callback.message.edit_text(
        '🧮 <b>Умный калькулятор</b>\n\n'
        'Отправь мне задачу любым удобным способом:\n\n'
        '✏️ <b>Текстом</b> — например: <code>2^10 + корень из 144</code>\n'
        '📷 <b>Фото</b> — сфотографируй задачу из учебника\n'
        '🎤 <b>Голосовым</b> — продиктуй задачу\n'
        '📄 <b>Документом</b> — прикрепи файл с задачами\n\n'
        'Для выхода напиши /cancel',
        parse_mode='HTML'
    )


# ========================
# Калькулятор — текст
# ========================

@router.message(CalculatorStates.waiting_for_input, F.text)
async def handle_text(message: Message, state: FSMContext):
    thinking_msg = await message.answer('🤔 Решаю задачу...')

    task = asyncio.create_task(solve_math(message.text))
    await state.update_data(current_task=task, cancelled=False)

    try:
        result = await task
        await thinking_msg.delete()
        await message.answer(f"\n{result}", parse_mode='HTML')
    except asyncio.CancelledError:
        try:
            await thinking_msg.delete()
        except:
            pass


# ========================
# Калькулятор — фото
# ========================

@router.message(CalculatorStates.waiting_for_input, F.photo)
async def handle_photo(message: Message, bot: Bot, state: FSMContext):
    thinking_msg = await message.answer('📷 Распознаю текст на фото...')

    photo = message.photo[-1]
    file_in_io = io.BytesIO()
    await bot.download(photo, destination=file_in_io)
    image_bytes = file_in_io.getvalue()

    await thinking_msg.edit_text('🤔 Решаю задачу...')

    task = asyncio.create_task(solve_from_image(image_bytes))
    await state.update_data(current_task=task, cancelled=False)

    try:
        result = await task
        await thinking_msg.delete()
        await message.answer(f"\n{result}", parse_mode='HTML')
    except asyncio.CancelledError:
        try:
            await thinking_msg.delete()
        except:
            pass


# ========================
# Калькулятор — голосовое
# ========================

@router.message(CalculatorStates.waiting_for_input, F.voice)
async def handle_voice(message: Message, bot: Bot, state: FSMContext):
    thinking_msg = await message.answer('🎤 Распознаю голосовое сообщение...')

    voice_buffer = io.BytesIO()
    await bot.download(message.voice, destination=voice_buffer)
    audio_bytes = voice_buffer.getvalue()

    api_key = os.getenv("YANDEX_API_KEY")
    folder_id = os.getenv("YANDEX_FOLDER_ID")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                headers={"Authorization": f"Api-Key {api_key}"},
                params={"lang": "ru-RU", "format": "oggopus", "folderId": folder_id},
                data=audio_bytes
            ) as resp:
                data = await resp.json()
                recognized_text = data.get("result", "")
    except Exception:
        recognized_text = ""

    if not recognized_text:
        await thinking_msg.delete()
        await message.answer('❌ Не удалось распознать голосовое сообщение. Попробуй написать задачу текстом.')
        return

    await thinking_msg.edit_text(f'🤔 Решаю: <i>{recognized_text}</i>...', parse_mode='HTML')

    task = asyncio.create_task(solve_math(recognized_text))
    await state.update_data(current_task=task, cancelled=False)

    try:
        result = await task
        await thinking_msg.delete()
        await message.answer(
            f'🎤 <b>Распознано:</b> <i>{recognized_text}</i>\n\n{result}',
            parse_mode='HTML'
        )
    except asyncio.CancelledError:
        try:
            await thinking_msg.delete()
        except:
            pass


# ========================
# Калькулятор — документ
# ========================

@router.message(CalculatorStates.waiting_for_input, F.document)
async def handle_document(message: Message, bot: Bot, state: FSMContext):
    doc = message.document
    mime = doc.mime_type or ""

    if "text" not in mime and "pdf" not in mime:
        await message.answer(
            '❌ Поддерживаются только текстовые файлы (.txt).\n'
            'Для PDF — сфотографируй страницу и пришли как фото.'
        )
        return

    thinking_msg = await message.answer('📄 Читаю документ...')

    file_in_io = io.BytesIO()
    await bot.download(doc, destination=file_in_io)
    file_bytes = file_in_io.getvalue()

    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("cp1251", errors="ignore")

    if not text.strip():
        await thinking_msg.delete()
        await message.answer('❌ Документ пустой или не удалось прочитать.')
        return

    await thinking_msg.edit_text('🤔 Решаю задачи из документа...')

    task = asyncio.create_task(solve_math(f"Задачи из документа:\n{text[:3000]}"))
    await state.update_data(current_task=task, cancelled=False)

    try:
        result = await task
        await thinking_msg.delete()
        await message.answer(f"\n{result}", parse_mode='HTML')
    except asyncio.CancelledError:
        try:
            await thinking_msg.delete()
        except:
            pass


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
async def tutor_handle_text(message: Message, state: FSMContext):
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
        await res_msg.edit_text(final_text, parse_mode='HTML')
        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])
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
        await res_msg.edit_text(f"📷 <b>Разбор фото:</b>\n\n{final_text}", parse_mode='HTML')
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
        await res_msg.edit_text(
            f"🗣 <i>\"{user_text}\"</i>\n\n{final_text}",
            parse_mode='HTML'
        )
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": final_text})
        await update_history(message.from_user.id, history[-10:])
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
        await res_msg.edit_text(f"📄 <b>Разбор документа:</b>\n\n{final_text}", parse_mode='HTML')
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
# Заглушка
# ========================

@router.callback_query(F.data == 'lectures')
async def open_lectures(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('📚 Лекции — скоро будет доступно!')