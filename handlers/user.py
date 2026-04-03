# import os
# import aiohttp
# import asyncio
# import io
# import time
# from aiogram import F, Router, Bot
# from aiogram.filters import CommandStart, Command
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import Message, CallbackQuery
#
# import keyboards.user_kb as kb
# from services.calculator import solve_math, solve_from_image
#
# router = Router()
#
#
# # FSM — состояния бота
# class CalculatorStates(StatesGroup):
#     waiting_for_input = State()
#     tutor_waiting = State()
#
#
# # ========================
# # Стартовые команды
# # ========================
#
# @router.message(CommandStart())
# async def cmd_start(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer(
#         'Привет! Я математический бот 🤖\nВыбери что хочешь сделать:',
#         reply_markup=kb.start,
#         parse_mode='HTML'
#     )
#
#
# @router.message(Command('help'))
# async def cmd_help(message: Message):
#     await message.answer("<b>🎓 Ваша математическая помощь здесь!</b>\n\n"
#         "Я — ИИ-репетитор, специализирующийся на математике. "
#         "Вот что я умею и как со мной работать:\n\n"
#         "<b>🔹 Возможности:</b>\n"
#         "• <b>Текст:</b> Просто напишите свой вопрос или условие задачи.\n"
#         "• <b>Фото:</b> Пришлите фото задачи, и я разберу её пошагово.\n"
#         "• <b>Голос:</b> Запишите ГС, если лень писать текст — я всё пойму.\n"
#         "• <b>Файлы:</b> Можете скинуть <code>.txt</code> с условиями.\n\n"
#         "<b>🔸 Полезные команды:</b>\n"
#         "• /start — перезапуск и главное меню.\n"
#         "• /cancel — отмена текущего диалога с репетитором.\n"
#         "• /help — это сообщение.\n\n"
#         "<b>⚠️ Важно:</b>\n"
#         "Я эксперт <b>только в математике</b>. Если вы спросите про историю или биологию, "
#         "я вежливо откажусь. Зато в уравнениях и теоремах мне нет равных! 😊\n\n"
#         "<i>Просто отправьте сообщение, чтобы начать обучение!</i>",
#                          parse_mode='HTML',
#                          message_effect_id='5104841245755180586')
#
#
# async def run_with_cancel(state: FSMContext, coro, thinking_msg, result_func):
#     """Запускает корутину и сохраняет задачу в state для возможной отмены"""
#     task = asyncio.create_task(coro)
#     await state.update_data(current_task=task)
#     try:
#         result = await task
#         return result
#     except asyncio.CancelledError:
#         await thinking_msg.delete()
#         return None
#
#
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
# # Калькулятор — отмена
# # ========================
#
# @router.message(Command('cancel'))
# async def cmd_cancel(message: Message, state: FSMContext):
#     # Отменяем текущую задачу если она есть
#     data = await state.get_data()
#     current_task = data.get("current_task")
#     if current_task and not current_task.done():
#         current_task.cancel()
#
#     await state.clear()
#     await message.answer(
#         'Вернулся в главное меню 👇',
#         reply_markup=kb.start
#     )
#
#
# # ========================
# # Калькулятор — текст
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.text)
# async def handle_text(message: Message):
#     thinking_msg = await message.answer('🤔 Решаю задачу...')
#     result = await solve_math(message.text)
#     await thinking_msg.delete()
#     await message.answer(result, parse_mode='HTML')
#
#
# # ========================
# # Калькулятор — фото
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.photo)
# async def handle_photo(message: Message, bot):
#     thinking_msg = await message.answer('📷 Распознаю текст на фото...')
#
#     # Берём фото в наилучшем качестве
#     photo = message.photo[-1]
#     file = await bot.get_file(photo.file_id)
#     file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
#
#     proxy = "socks5://127.0.0.1:12334"
#     async with aiohttp.ClientSession() as session:
#         async with session.get(file_url, proxy=proxy) as resp:
#             image_bytes = await resp.read()
#
#     await thinking_msg.edit_text('🤔 Решаю задачу...')
#
#     from services.calculator import solve_from_image
#     result = await solve_from_image(image_bytes)
#
#     await thinking_msg.delete()
#     await message.answer(result, parse_mode='HTML')
#
#
# # ========================
# # Калькулятор — голосовое
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.voice)
# async def handle_voice(message: Message, bot):
#     thinking_msg = await message.answer('🎤 Распознаю голосовое сообщение...')
#
#     voice = message.voice
#     file = await bot.get_file(voice.file_id)
#     file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
#
#     proxy = "socks5://127.0.0.1:12334"
#     async with aiohttp.ClientSession() as session:
#         async with session.get(file_url, proxy=proxy) as resp:
#             audio_bytes = await resp.read()
#
#     api_key = os.getenv("YANDEX_API_KEY")
#
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                 "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
#                 headers={"Authorization": f"Api-Key {api_key}"},
#                 params={"lang": "ru-RU", "format": "oggopus"},
#                 data=audio_bytes
#             ) as resp:
#                 data = await resp.json()
#                 recognized_text = data.get("result", "")
#     except Exception as e:
#         recognized_text = ""
#
#     if not recognized_text:
#         await thinking_msg.delete()
#         await message.answer(
#             '❌ Не удалось распознать голосовое сообщение. '
#             'Попробуй написать задачу текстом.'
#         )
#         return
#
#     await thinking_msg.edit_text(f'🤔 Решаю: <i>{recognized_text}</i>...', parse_mode='HTML')
#
#     from services.calculator import solve_math
#     result = await solve_math(recognized_text)
#
#     await thinking_msg.delete()
#     await message.answer(
#         f'🎤 <b>Распознано:</b> <i>{recognized_text}</i>\n\n{result}',
#         parse_mode='HTML'
#     )
#
# # ========================
# # Калькулятор — документ
# # ========================
#
# @router.message(CalculatorStates.waiting_for_input, F.document)
# async def handle_document(message: Message, bot):
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
#
#     file = await bot.get_file(doc.file_id)
#     file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
#
#     proxy = "socks5://127.0.0.1:12334"
#     async with aiohttp.ClientSession() as session:
#         async with session.get(file_url, proxy=proxy) as resp:
#             file_bytes = await resp.read()
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
#
#     from services.calculator import solve_math
#     result = await solve_math(f"Задачи из документа:\n{text[:3000]}")
#
#     await thinking_msg.delete()
#     await message.answer(f"\n{result}", parse_mode='HTML')
#
#
# # ========================
# # ИИ-репетитор — вход
# # ========================
#
# @router.callback_query(F.data == 'ai-tutor')
# async def open_tutor(callback: CallbackQuery, state: FSMContext):
#     await callback.answer()
#     await state.set_state(CalculatorStates.tutor_waiting)
#     await state.update_data(tutor_history=[])  # сбрасываем историю при входе
#     await callback.message.edit_text(
#         '🎓 <b>ИИ-репетитор по математике</b>\n\n'
#         'Я помогу разобраться с любой математической темой!\n\n'
#         '✏️ <b>Текстом</b> — задай вопрос по теме\n'
#         '📷 <b>Фото</b> — пришли страницу из учебника\n'
#         '🎤 <b>Голосовым</b> — задай вопрос голосом\n'
#         '📄 <b>Документом</b> — прикрепи файл с вопросами\n\n'
#         'Для выхода напиши /cancel',
#         parse_mode='HTML'
#     )
#
#
# # ========================
# # ИИ-репетитор — текст
# # ========================
#
# # @router.message(CalculatorStates.tutor_waiting, F.text)
# # async def tutor_handle_text(message: Message, state: FSMContext):
# #     thinking_msg = await message.answer('🤔 Думаю над ответом...')
# #
# #     data = await state.get_data()
# #     history = data.get("tutor_history", [])
# #
# #     from services.tutor import ask_tutor
# #     result = await ask_tutor(message.text, history)
# #
# #     # Добавляем в историю
# #     history.append({"role": "user", "content": message.text})
# #     history.append({"role": "assistant", "content": result})
# #     await state.update_data(tutor_history=history)
# #
# #     await thinking_msg.delete()
# #     await message.answer(f"\n{result}", parse_mode='HTML')
#
#
# @router.message(CalculatorStates.tutor_waiting, F.text)
# async def tutor_handle_text(message: Message, state: FSMContext):
#     res_msg = await message.answer("🤔 <b>Думаю...</b>", parse_mode='HTML')
#     data = await state.get_data()
#     history = data.get("tutor_history", [])
#
#     from services.tutor import ask_tutor, clean_response
#     full_text, displayed_text = "", ""
#     last_edit_time = 0
#
#     async for chunk in ask_tutor(message.text, history):
#         full_text += chunk
#         current_clean = clean_response(full_text)
#         if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
#             try:
#                 await res_msg.edit_text(f"{current_clean} ▌", parse_mode='HTML')
#                 displayed_text, last_edit_time = current_clean, time.time()
#             except:
#                 continue
#
#     final_text = clean_response(full_text)
#     await res_msg.edit_text(final_text, parse_mode='HTML')
#     history.append({"role": "user", "content": message.text})
#     history.append({"role": "assistant", "content": final_text})
#     await state.update_data(tutor_history=history[-10:])
#
#
# # ========================
# # ИИ-репетитор — фото
# # ========================
#
# import io
# import time
# from aiogram import Bot
#
#
# @router.message(CalculatorStates.tutor_waiting, F.photo)
# async def tutor_handle_photo(message: Message, state: FSMContext, bot: Bot):
#     # 1. Начальное сообщение
#     res_msg = await message.answer("📸 <b>Изучаю фото...</b>", parse_mode='HTML')
#
#     try:
#         # 2. Скачиваем фото самым надежным способом (через bot.download)
#         photo = message.photo[-1]
#         file_in_io = io.BytesIO()
#         await bot.download(photo, destination=file_in_io)
#         image_bytes = file_in_io.getvalue()
#
#         await res_msg.edit_text("🤔 <b>Распознаю текст и задачу...</b>", parse_mode='HTML')
#
#         # 3. Настройка стриминга
#         data = await state.get_data()
#         history = data.get("tutor_history", [])
#
#         from services.tutor import ask_tutor_image, clean_response
#         full_text, displayed_text = "", ""
#         last_edit_time = 0
#
#         # 4. Плавный вывод ответа
#         async for chunk in ask_tutor_image(image_bytes, history):
#             full_text += chunk
#             current_clean = clean_response(full_text)
#
#             # Обновляем сообщение раз в 0.7 сек, чтобы не злить Telegram
#             if current_clean != displayed_text and (time.time() - last_edit_time) > 0.7:
#                 try:
#                     await res_msg.edit_text(f"📷 <b>Разбор фото:</b>\n\n{current_clean} ▌", parse_mode='HTML')
#                     displayed_text, last_edit_time = current_clean, time.time()
#                 except:
#                     continue
#
#         # Финальный результат без курсора
#         final_text = clean_response(full_text)
#         await res_msg.edit_text(f"📷 <b>Разбор фото:</b>\n\n{final_text}", parse_mode='HTML')
#
#     except Exception as e:
#         await res_msg.edit_text(f"❌ Ошибка при обработке фото: {str(e)}")
#
#
# # ========================
# # ИИ-репетитор — голосовое
# # ========================
#
# import io
# import time
# from aiogram import Bot, F
# from services.tutor import speech_to_text, ask_tutor, clean_response
#
#
# @router.message(CalculatorStates.tutor_waiting, F.voice)
# async def tutor_handle_voice(message: Message, state: FSMContext, bot: Bot):
#     # 1. Сразу даем обратную связь
#     res_msg = await message.answer("🎤 <b>Слушаю...</b>", parse_mode='HTML')
#
#     try:
#         # 2. Скачиваем ГС в память без использования session.get
#         voice_buffer = io.BytesIO()
#         await bot.download(message.voice, destination=voice_buffer)
#         voice_bytes = voice_buffer.getvalue()
#
#         # 3. Переводим голос в текст
#         user_text = await speech_to_text(voice_bytes)
#
#         if not user_text:
#             await res_msg.edit_text("❌ Не удалось распознать речь. Попробуйте сказать четче.")
#             return
#
#         # Показываем пользователю, что мы его поняли
#         await res_msg.edit_text(f"🗣 <i>Вы сказали: \"{user_text}\"</i>\n\n🤔 <b>Думаю...</b>", parse_mode='HTML')
#
#         # 4. Настройка плавного вывода
#         data = await state.get_data()
#         history = data.get("tutor_history", [])
#         full_text, displayed_text, last_edit_time = "", "", 0
#
#         async for chunk in ask_tutor(user_text, history):
#             full_text += chunk
#             current_clean = clean_response(full_text)
#
#             # Обновляем сообщение раз в 0.6 сек
#             if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
#                 try:
#                     header = f"🗣 <i>\"{user_text}\"</i>\n\n"
#                     await res_msg.edit_text(f"{header}{current_clean} ▌", parse_mode='HTML')
#                     displayed_text, last_edit_time = current_clean, time.time()
#                 except:
#                     continue
#
#         # Финальный результат
#         final_text = clean_response(full_text)
#         await res_msg.edit_text(f"🗣 <i>\"{user_text}\"</i>\n\n{final_text}", parse_mode='HTML')
#
#         # Сохраняем в историю
#         history.append({"role": "user", "content": user_text})
#         history.append({"role": "assistant", "content": final_text})
#         await state.update_data(tutor_history=history[-10:])
#
#     except Exception as e:
#         await res_msg.edit_text(f"❌ Ошибка ГС: {str(e)}")
#
#
# # ========================
# # ИИ-репетитор — документ
# # ========================
#
# @router.message(CalculatorStates.tutor_waiting, F.document)
# async def tutor_handle_document(message: Message, state: FSMContext, bot: Bot):
#     res_msg = await message.answer("📄 <b>Читаю документ...</b>", parse_mode='HTML')
#
#     doc = message.document
#
#     try:
#         # 1. Скачиваем файл встроенным методом aiogram (это надежнее)
#         file_in_io = io.BytesIO()
#         await bot.download(doc, destination=file_in_io)
#         file_bytes = file_in_io.getvalue()
#
#         # 2. Декодируем содержимое
#         try:
#             text = file_bytes.decode("utf-8")
#         except UnicodeDecodeError:
#             text = file_bytes.decode("cp1251", errors="ignore")
#
#         if not text.strip():
#             await res_msg.edit_text("❌ Документ пустой.")
#             return
#
#         await res_msg.edit_text("🤔 <b>Анализирую содержимое...</b>", parse_mode='HTML')
#
#         # 3. Подготовка к плавному выводу
#         data = await state.get_data()
#         history = data.get("tutor_history", [])
#
#         from services.tutor import ask_tutor, clean_response
#         full_text, displayed_text = "", ""
#         last_edit_time = 0
#
#         # 4. Плавный вывод ответа
#         async for chunk in ask_tutor(f"Проанализируй этот текст из файла:\n{text[:3000]}", history):
#             full_text += chunk
#             current_clean = clean_response(full_text)
#
#             # Обновляем сообщение раз в 0.6 сек
#             if current_clean != displayed_text and (time.time() - last_edit_time) > 0.6:
#                 try:
#                     await res_msg.edit_text(f"📄 <b>Разбор документа:</b>\n\n{current_clean} ▌", parse_mode='HTML')
#                     displayed_text, last_edit_time = current_clean, time.time()
#                 except:
#                     continue
#
#         # Финальный результат
#         final_text = clean_response(full_text)
#         await res_msg.edit_text(f"📄 <b>Разбор документа:</b>\n\n{final_text}", parse_mode='HTML')
#
#         # Сохраняем в историю
#         history.append({"role": "user", "content": f"Файл: {doc.file_name}"})
#         history.append({"role": "assistant", "content": final_text})
#         await state.update_data(tutor_history=history[-10:])
#
#     except Exception as e:
#         await res_msg.edit_text(f"❌ Ошибка при чтении файла: {str(e)}")
#
#
# # ======================== ЗАаглушка
#
# @router.callback_query(F.data == 'lectures')
# async def open_lectures(callback: CallbackQuery):
#     await callback.answer()
#     await callback.message.edit_text('📚 Лекции — скоро будет доступно!')

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
from handlers.admin import is_admin
from services.calculator import solve_math, solve_from_image
from database.models import register_user

router = Router()


# FSM — состояния бота
class CalculatorStates(StatesGroup):
    waiting_for_input = State()
    tutor_waiting = State()


# ========================
# Стартовые команды
# ========================

ADMIN_ID = int(os.getenv("ADMIN_ID"))

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # 1. Логика отмены текущих задач
    data = await state.get_data()
    task = data.get("current_task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # 2. Сохранение пользователя в БД
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    await register_user(user_id, username)

    # 3. ПРОВЕРКА НА АДМИНА (Критически важно!)
    # Мы создаем локальную переменную is_user_admin для этого конкретного сообщения
    is_user_admin = (user_id == ADMIN_ID)

    # 4. Очистка состояния и ответ
    await state.clear()
    await message.answer(
        'Привет! Я математический бот 🤖\nВыбери что хочешь сделать:',
        reply_markup=kb.get_start_kb(is_user_admin), # Передаем результат проверки
        parse_mode='HTML'
    )


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
        reply_markup=kb.get_start_kb(is_admin)
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
    await state.update_data(tutor_history=[], current_task=None, cancelled=False)
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
    data = await state.get_data()
    history = data.get("tutor_history", [])

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
        await state.update_data(tutor_history=history[-10:], current_task=None)
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
        await state.update_data(tutor_history=history[-10:], current_task=None)

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
        await state.update_data(tutor_history=history[-10:], current_task=None)

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
        await state.update_data(tutor_history=history[-10:], current_task=None)

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