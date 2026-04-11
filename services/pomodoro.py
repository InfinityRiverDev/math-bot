import asyncio
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from database.stats_models import log_activity

router = Router()


# =========================
# ⏱ FSM состояния
# =========================
class PomodoroStates(StatesGroup):
    idle = State()                  # Ожидание запуска
    working = State()               # Идёт рабочий интервал
    on_break = State()              # Идёт перерыв
    paused = State()                # Пауза
    custom_work = State()           # Ввод рабочего времени
    custom_short_break = State()    # Ввод короткого перерыва
    custom_long_break = State()     # Ввод длинного перерыва
    custom_cycles = State()         # Ввод кол-ва циклов до длинного перерыва


# =========================
# ⏱ Настройки по умолчанию (в секундах)
# =========================
WORK_TIME = 25 * 60
SHORT_BREAK = 5 * 60
LONG_BREAK = 15 * 60
LONG_BREAK_AFTER = 4  # длинный перерыв после N циклов


# =========================
# 🎛 Клавиатуры
# =========================
def kb_start_pomodoro() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Старт (25/5)", callback_data="pomo_start_default"),
            InlineKeyboardButton(text="⚙️ Настроить", callback_data="pomo_custom"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="focus")]
    ])


def kb_running() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ Пауза", callback_data="pomo_pause"),
            InlineKeyboardButton(text="⏹ Стоп", callback_data="pomo_stop"),
        ]
    ])


def kb_paused() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Продолжить", callback_data="pomo_resume"),
            InlineKeyboardButton(text="⏹ Стоп", callback_data="pomo_stop"),
        ]
    ])


def kb_break() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏭ Пропустить перерыв", callback_data="pomo_skip_break"),
            InlineKeyboardButton(text="⏹ Стоп", callback_data="pomo_stop"),
        ]
    ])


def kb_after_session() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Новый сеанс", callback_data="pomodoro_timer"),
            InlineKeyboardButton(text="⬅️ В меню", callback_data="focus"),
        ]
    ])


# =========================
# 🔧 Вспомогательные функции
# =========================
def fmt_time(seconds: int) -> str:
    """Форматирует секунды в MM:SS"""
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def progress_bar(elapsed: int, total: int, length: int = 10) -> str:
    """Визуальный прогресс-бар"""
    filled = int(length * elapsed / total) if total > 0 else 0
    return "🟥" * filled + "⬜" * (length - filled)


async def safe_edit(msg, text: str, markup=None):
    """Редактирует сообщение, игнорируя 'not modified'"""
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


# =========================
# 🍅 Вход в меню помодоро
# =========================
@router.callback_query(F.data == "pomodoro_timer")
async def pomo_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    # Если уже идёт таймер — показываем статус
    current_state = await state.get_state()
    if current_state in (PomodoroStates.working, PomodoroStates.on_break, PomodoroStates.paused):
        data = await state.get_data()
        cycles = data.get("cycles_done", 0)
        await callback.answer("⏱ Таймер уже запущен!", show_alert=True)
        return

    await state.set_state(PomodoroStates.idle)
    await callback.message.edit_text(
        "🍅 <b>Таймер Помодоро</b>\n\n"
        "Техника Помодоро помогает сохранять фокус:\n"
        "• <b>25 мин</b> — работа\n"
        "• <b>5 мин</b> — короткий перерыв\n"
        "• После 4 циклов — <b>15 мин</b> длинный перерыв\n\n"
        "Выбери режим:",
        reply_markup=kb_start_pomodoro(),
        parse_mode='HTML'
    )


# =========================
# ▶️ Старт со стандартными настройками
# =========================
@router.callback_query(F.data == "pomo_start_default")
async def pomo_start_default(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(
        work_time=WORK_TIME,
        short_break=SHORT_BREAK,
        long_break=LONG_BREAK,
        cycles_done=0,
        pomo_msg_id=callback.message.message_id,
        paused_at=None,
        stop_flag=False,
        skip_break_flag=False,
    )
    await _start_work_session(callback, state)


# =========================
# 🔁 Запуск рабочего интервала
# =========================
async def _start_work_session(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PomodoroStates.working)
    data = await state.get_data()
    cycles = data.get("cycles_done", 0)
    work_time = data.get("work_time", WORK_TIME)

    msg = callback.message
    text = (
        f"🍅 <b>Помодоро #{cycles + 1} — Работа</b>\n\n"
        f"⏱ Осталось: <b>{fmt_time(work_time)}</b>\n"
        f"{progress_bar(0, work_time)}\n\n"
        f"Сосредоточься и работай! 💪"
    )
    await safe_edit(msg, text, kb_running())

    # Запускаем фоновую задачу
    task = asyncio.create_task(_run_timer(callback, state, work_time, phase="work"))
    await state.update_data(current_pomo_task=task)


# =========================
# ⏱ Основной цикл таймера
# =========================
async def _run_timer(callback: CallbackQuery, state: FSMContext, total: int, phase: str):
    """
    Тикает каждую секунду и обновляет сообщение каждые 5 секунд.
    В конце — уведомляет и переходит к следующей фазе.
    """
    UPDATE_INTERVAL = 5   # обновляем отображение каждые 5 сек (баланс между точностью и лимитами API)
    TICK = 1              # внутренний тик — 1 секунда
    elapsed = 0
    last_update = 0
    msg = callback.message

    while elapsed < total:
        await asyncio.sleep(TICK)

        # Проверяем флаги
        data = await state.get_data()
        if data.get("stop_flag"):
            return

        # Пауза: ждём снятия паузы
        if await state.get_state() == PomodoroStates.paused:
            while await state.get_state() == PomodoroStates.paused:
                await asyncio.sleep(1)
                data = await state.get_data()
                if data.get("stop_flag"):
                    return
            continue

        elapsed += TICK

        # Пропуск перерыва
        if phase == "break" and data.get("skip_break_flag"):
            await state.update_data(skip_break_flag=False)
            break

        # Обновляем сообщение раз в UPDATE_INTERVAL секунд
        if elapsed - last_update < UPDATE_INTERVAL and elapsed < total:
            continue
        last_update = elapsed

        remaining = total - elapsed
        data = await state.get_data()
        cycles = data.get("cycles_done", 0)

        if phase == "work":
            label = f"🍅 <b>Помодоро #{cycles + 1} — Работа</b>"
            footer = "Сосредоточься и работай! 💪"
            markup = kb_running()
        else:
            label = f"☕ <b>Перерыв</b>"
            footer = "Отдохни, встань, потянись! 🧘"
            markup = kb_break()

        text = (
            f"{label}\n\n"
            f"⏱ Осталось: <b>{fmt_time(remaining)}</b>\n"
            f"{progress_bar(elapsed, total)}\n\n"
            f"{footer}"
        )
        await safe_edit(msg, text, markup)

    # Таймер завершился
    data = await state.get_data()
    if data.get("stop_flag"):
        return

    if phase == "work":
        await _on_work_done(callback, state)
    else:
        await _on_break_done(callback, state)


# =========================
# ✅ Конец рабочего интервала
# =========================
async def _on_work_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cycles_done = data.get("cycles_done", 0) + 1
    await state.update_data(cycles_done=cycles_done)

    short_break = data.get("short_break", SHORT_BREAK)
    long_break = data.get("long_break", LONG_BREAK)

    long_break_after = data.get("long_break_after", LONG_BREAK_AFTER)
    is_long = cycles_done % long_break_after == 0
    break_time = long_break if is_long else short_break
    break_label = "длинный" if is_long else "короткий"

    msg = callback.message
    await safe_edit(
        msg,
        f"✅ <b>Помодоро #{cycles_done} завершён!</b>\n\n"
        f"🏆 Всего циклов: <b>{cycles_done}</b>\n\n"
        f"☕ Начинается <b>{break_label} перерыв</b> — {fmt_time(break_time)}\n"
        f"{progress_bar(0, break_time)}",
        kb_break()
    )

    # Уведомление
    try:
        await callback.bot.send_message(
            callback.from_user.id,
            f"🔔 Помодоро #{cycles_done} завершён! Время отдохнуть ☕"
        )
    except Exception:
        pass

    await state.set_state(PomodoroStates.on_break)
    task = asyncio.create_task(_run_timer(callback, state, break_time, phase="break"))
    await state.update_data(current_pomo_task=task)

    from services.xp import give_xp
    await give_xp(callback.bot, callback.from_user.id, "pomodoro_completed")
    # Бонус за 5 циклов:
    if cycles_done % 5 == 0:
        await give_xp(callback.bot, callback.from_user.id, "pomodoro_5cycles")

    log_activity()


# =========================
# ☕ Конец перерыва
# =========================
async def _on_break_done(callback: CallbackQuery, state: FSMContext):
    msg = callback.message
    data = await state.get_data()
    cycles = data.get("cycles_done", 0)

    # Уведомление
    try:
        await callback.bot.send_message(
            callback.from_user.id,
            f"🔔 Перерыв закончился! Пора работать 💪 (Цикл #{cycles + 1})"
        )
    except Exception:
        pass

    await _start_work_session(callback, state)


# =========================
# ⏸ Пауза
# =========================
@router.callback_query(F.data == "pomo_pause")
async def pomo_pause(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏸ Пауза")
    await state.set_state(PomodoroStates.paused)

    data = await state.get_data()
    msg = callback.message
    await safe_edit(
        msg,
        "⏸ <b>Пауза</b>\n\nТаймер приостановлен.\nНажми «Продолжить» когда будешь готов.",
        kb_paused()
    )


# =========================
# ▶️ Продолжить после паузы
# =========================
@router.callback_query(F.data == "pomo_resume")
async def pomo_resume(callback: CallbackQuery, state: FSMContext):
    await callback.answer("▶️ Продолжаем!")

    data = await state.get_data()
    # Определяем какая фаза была до паузы по наличию данных
    # Восстанавливаем состояние working или on_break
    cycles = data.get("cycles_done", 0)

    # Смотрим, была ли пауза во время работы или перерыва
    # Для простоты: если задача ещё не завершена — просто снимаем паузу
    # Фаза определяется тем, что таймер сам знает phase
    await state.set_state(PomodoroStates.working)

    msg = callback.message
    await safe_edit(
        msg,
        f"🍅 <b>Помодоро #{cycles + 1} — Работа</b>\n\n"
        f"▶️ Продолжаем!\n\n"
        f"Сосредоточься и работай! 💪",
        kb_running()
    )


# =========================
# ⏭ Пропустить перерыв
# =========================
@router.callback_query(F.data == "pomo_skip_break")
async def pomo_skip_break(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏭ Перерыв пропущен")
    await state.update_data(skip_break_flag=True)


# =========================
# ⏹ Стоп
# =========================
@router.callback_query(F.data == "pomo_stop")
async def pomo_stop(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    cycles = data.get("cycles_done", 0)

    # Останавливаем задачу
    await state.update_data(stop_flag=True)
    task = data.get("current_pomo_task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await state.clear()

    await safe_edit(
        callback.message,
        f"⏹ <b>Сеанс завершён</b>\n\n"
        f"🏆 Завершено помодоро: <b>{cycles}</b>\n\n"
        f"Отличная работа! Возвращайся когда будешь готов 🍅",
        kb_after_session()
    )


def kb_custom_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="pomo_custom_cancel")]
    ])


def kb_custom_confirm(work: int, short_b: int, long_b: int, cycles: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Запустить", callback_data="pomo_start_custom")],
        [InlineKeyboardButton(text="✏️ Изменить снова", callback_data="pomo_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="pomodoro_timer")],
    ])


# =========================
# ⚙️ Кастомные настройки — шаг 1: рабочее время
# =========================
@router.callback_query(F.data == "pomo_custom")
async def pomo_custom(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PomodoroStates.custom_work)
    await callback.message.edit_text(
        "⚙️ <b>Кастомные настройки — шаг 1/4</b>\n\n"
        "⏱ Введи длину <b>рабочего интервала</b> в минутах:\n\n"
        "<i>Например: 25 (рекомендуется от 15 до 60)</i>",
        reply_markup=kb_custom_cancel(),
        parse_mode='HTML'
    )


@router.message(PomodoroStates.custom_work)
async def pomo_custom_work_input(message: Message, state: FSMContext):
    value = _parse_minutes(message.text)
    if value is None:
        await message.answer(
            "❌ Введи целое число от 1 до 120.\nНапример: <code>25</code>",
            reply_markup=kb_custom_cancel(),
            parse_mode='HTML'
        )
        return

    await state.update_data(custom_work_time=value * 60)
    await state.set_state(PomodoroStates.custom_short_break)
    await message.answer(
        f"✅ Рабочий интервал: <b>{value} мин</b>\n\n"
        "⚙️ <b>Шаг 2/4</b>\n\n"
        "☕ Введи длину <b>короткого перерыва</b> в минутах:\n\n"
        "<i>Например: 5</i>",
        reply_markup=kb_custom_cancel(),
        parse_mode='HTML'
    )


@router.message(PomodoroStates.custom_short_break)
async def pomo_custom_short_break_input(message: Message, state: FSMContext):
    value = _parse_minutes(message.text)
    if value is None:
        await message.answer(
            "❌ Введи целое число от 1 до 60.\nНапример: <code>5</code>",
            reply_markup=kb_custom_cancel(),
            parse_mode='HTML'
        )
        return

    await state.update_data(custom_short_break=value * 60)
    await state.set_state(PomodoroStates.custom_long_break)
    await message.answer(
        f"✅ Короткий перерыв: <b>{value} мин</b>\n\n"
        "⚙️ <b>Шаг 3/4</b>\n\n"
        "🛋 Введи длину <b>длинного перерыва</b> в минутах:\n\n"
        "<i>Например: 15</i>",
        reply_markup=kb_custom_cancel(),
        parse_mode='HTML'
    )


@router.message(PomodoroStates.custom_long_break)
async def pomo_custom_long_break_input(message: Message, state: FSMContext):
    value = _parse_minutes(message.text)
    if value is None:
        await message.answer(
            "❌ Введи целое число от 1 до 120.\nНапример: <code>15</code>",
            reply_markup=kb_custom_cancel(),
            parse_mode='HTML'
        )
        return

    await state.update_data(custom_long_break=value * 60)
    await state.set_state(PomodoroStates.custom_cycles)
    await message.answer(
        f"✅ Длинный перерыв: <b>{value} мин</b>\n\n"
        "⚙️ <b>Шаг 4/4</b>\n\n"
        "🔁 После скольких рабочих циклов делать <b>длинный перерыв</b>?\n\n"
        "<i>Например: 4 (стандарт по технике Помодоро)</i>",
        reply_markup=kb_custom_cancel(),
        parse_mode='HTML'
    )


@router.message(PomodoroStates.custom_cycles)
async def pomo_custom_cycles_input(message: Message, state: FSMContext):
    try:
        value = int(message.text.strip())
        if not (1 <= value <= 20):
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Введи целое число от 1 до 20.\nНапример: <code>4</code>",
            reply_markup=kb_custom_cancel(),
            parse_mode='HTML'
        )
        return

    await state.update_data(custom_long_break_after=value)
    data = await state.get_data()

    w = data["custom_work_time"] // 60
    sb = data["custom_short_break"] // 60
    lb = data["custom_long_break"] // 60
    ca = value

    await state.set_state(PomodoroStates.idle)
    await message.answer(
        "✅ <b>Настройки сохранены!</b>\n\n"
        f"🍅 Работа: <b>{w} мин</b>\n"
        f"☕ Короткий перерыв: <b>{sb} мин</b>\n"
        f"🛋 Длинный перерыв: <b>{lb} мин</b>\n"
        f"🔁 Длинный перерыв после: <b>{ca} циклов</b>\n\n"
        "Нажми «Запустить» чтобы начать:",
        reply_markup=kb_custom_confirm(w, sb, lb, ca),
        parse_mode='HTML'
    )


# =========================
# ▶️ Старт с кастомными настройками
# =========================
@router.callback_query(F.data == "pomo_start_custom")
async def pomo_start_custom(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    await state.update_data(
        work_time=data.get("custom_work_time", WORK_TIME),
        short_break=data.get("custom_short_break", SHORT_BREAK),
        long_break=data.get("custom_long_break", LONG_BREAK),
        long_break_after=data.get("custom_long_break_after", LONG_BREAK_AFTER),
        cycles_done=0,
        pomo_msg_id=callback.message.message_id,
        paused_at=None,
        stop_flag=False,
        skip_break_flag=False,
    )
    await _start_work_session(callback, state)


# =========================
# ❌ Отмена настройки
# =========================
@router.callback_query(F.data == "pomo_custom_cancel")
async def pomo_custom_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PomodoroStates.idle)
    await callback.message.edit_text(
        "🍅 <b>Таймер Помодоро</b>\n\n"
        "Техника Помодоро помогает сохранять фокус:\n"
        "• <b>25 мин</b> — работа\n"
        "• <b>5 мин</b> — короткий перерыв\n"
        "• После 4 циклов — <b>15 мин</b> длинный перерыв\n\n"
        "Выбери режим:",
        reply_markup=kb_start_pomodoro(),
        parse_mode='HTML'
    )


# =========================
# 🔧 Парсинг минут с валидацией
# =========================
def _parse_minutes(text: str, min_val: int = 1, max_val: int = 120) -> int | None:
    try:
        value = int(text.strip())
        if min_val <= value <= max_val:
            return value
    except (ValueError, AttributeError):
        pass
    return None