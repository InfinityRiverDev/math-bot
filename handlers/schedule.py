"""
handlers/schedule.py

Расписание с листанием по дням:
- При открытии показывает текущий день
- Кнопки ◀️ ▶️ для листания по дням недели
- Кнопка 📅 для ввода произвольной даты (формат ДД.ММ.ГГГГ)
- Кнопка 🔄 для перехода к сегодняшнему дню
- Данные недели кэшируются в FSMContext — запрос к API делается один раз на неделю
"""

import aiohttp
from datetime import datetime, date, timedelta
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
import keyboards.user_kb as kb
from database.models import get_user_profile
from handlers.registration import check_knrtu_auth
from database.stats_models import log_activity

router = Router()

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

ABBR_EMOJI = {
    "лекц": "📖", "лек": "📖",
    "пз":   "✏️", "пр": "✏️", "сем": "✏️",
    "лр":   "🔬", "лаб": "🔬",
    "конс": "💬", "зач": "📝", "экз": "📝",
}


# =========================
# FSM — ожидание ввода даты
# =========================
class ScheduleStates(StatesGroup):
    waiting_date_input = State()


# =========================
# Утилиты: академический год и неделя
# =========================

def get_academic_year_start() -> date:
    today = date.today()
    year = today.year if today.month >= 9 else today.year - 1
    return date(year, 9, 1)


def get_academic_year() -> int:
    return get_academic_year_start().year


def get_knrtu_week_number(for_date: date = None) -> int:
    target = for_date or date.today()
    sep1 = get_academic_year_start()
    days_to_monday = sep1.weekday()
    first_monday = sep1 - timedelta(days=days_to_monday)
    delta = target - first_monday
    return max(1, delta.days // 7 + 1)


def date_to_weekday(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, "%d.%m.%Y")
        return d.isoweekday()  # 1=пн...7=вс
    except Exception:
        return 0


def get_lesson_emoji(abbr: str) -> str:
    abbr_lower = (abbr or "").lower().strip()
    for key, emoji in ABBR_EMOJI.items():
        if key in abbr_lower:
            return emoji
    return "📌"


def monday_of_week(for_date: date) -> date:
    return for_date - timedelta(days=for_date.weekday())


# =========================
# Парсинг ответа API → словарь {weekday: [уроки]}
# =========================

def parse_schedule_days(api_response: dict) -> dict[int, list]:
    """Возвращает {номер_дня_недели(1-7): [список уроков]}."""
    if not isinstance(api_response, dict) or not api_response.get("status"):
        return {}

    time_slots = api_response.get("objects", {})
    days: dict[int, list] = {}

    for slot_num, slot_data in time_slots.items():
        time_s = slot_data.get("time_start", "?")
        time_e = slot_data.get("time_end", "?")
        for lesson in slot_data.get("objects", []):
            weekday = date_to_weekday(lesson.get("date_lesson", ""))
            if weekday == 0:
                weekday = lesson.get("d_start_weekday", 0)
            if weekday == 0:
                continue
            days.setdefault(weekday, []).append({
                **lesson,
                "_time_start": time_s,
                "_time_end": time_e,
                "_slot_num": int(slot_num),
            })

    return days


# =========================
# Форматирование одного дня
# =========================

def format_day(days: dict, target_date: date, week_num: int) -> str:
    today = date.today()
    weekday = target_date.isoweekday()  # 1=пн...7=вс
    day_name = DAYS_RU[weekday - 1]
    date_str = target_date.strftime("%d.%m.%Y")
    is_today = target_date == today

    header_parts = [f"📅 <b>Неделя №{week_num}</b>"]
    if is_today:
        header_parts.append("📍 <b>Сегодня</b>")

    header_parts.append(f"\n<b>━━ {day_name}, {date_str} ━━</b>")
    lines = ["\n".join(header_parts)]

    lessons = days.get(weekday, [])

    if not lessons:
        lines.append("\n📭 <b>Занятий нет</b>")
        return "\n".join(lines)

    for lesson in sorted(lessons, key=lambda x: x.get("_slot_num", 0)):
        time_s = lesson["_time_start"]
        time_e = lesson["_time_end"]
        slot_n = lesson["_slot_num"]
        subj    = lesson.get("id_discipline_name") or "—"
        teacher = lesson.get("id_e_fio") or ""
        room    = lesson.get("id_premises_name") or ""
        abbr    = lesson.get("idk_lesson_abbr") or ""
        note    = lesson.get("note") or ""

        emoji = get_lesson_emoji(abbr)
        abbr_text = f" <i>[{abbr}]</i>" if abbr else ""

        line = f"\n{emoji} <b>{slot_n} пара  {time_s}–{time_e}</b>{abbr_text}\n    📚 {subj}"
        if teacher:
            line += f"\n    👤 {teacher}"
        if room:
            line += f"\n   🚪 {room}"
        if note:
            line += f"\n    📎 {note}"
        lines.append(line)

    return "\n".join(lines)


# =========================
# Клавиатура листания
# =========================

def get_nav_kb(target_date: date) -> InlineKeyboardMarkup:
    today = date.today()
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    prev_str = prev_date.strftime("%d.%m.%Y")
    next_str = next_date.strftime("%d.%m.%Y")
    today_str = today.strftime("%d.%m.%Y")

    is_today = target_date == today

    nav_row = [
        InlineKeyboardButton(text="◀️", callback_data=f"sched_day_{prev_str}"),
        InlineKeyboardButton(
            text="📍 Сегодня" if not is_today else "• Сегодня •",
            callback_data=f"sched_day_{today_str}"
        ),
        InlineKeyboardButton(text="▶️", callback_data=f"sched_day_{next_str}"),
    ]

    return InlineKeyboardMarkup(inline_keyboard=[
        nav_row,
        [InlineKeyboardButton(text="📅 Ввести дату", callback_data="sched_enter_date")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="education")],
    ])


# =========================
# API: загрузка расписания
# =========================

async def fetch_schedule(token: str, group_id: int, week_num: int) -> dict:
    acad_year = get_academic_year()
    print(f"Fetching schedule: year={acad_year}, group={group_id}, week={week_num}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://rest.kstu.ru/restapi/schedule/load-schedules/",
                headers={
                    "accept": "*/*",
                    "accept-language": "ru,en;q=0.9",
                    "authorization": f"Token {token}",
                    "content-type": "application/json",
                    "Referer": "https://one.kstu.ru/"
                },
                json={
                    "year": acad_year,
                    "list_groups": [group_id],
                    "id_e": [],
                    "numb_week": week_num
                }
            ) as resp:
                data = await resp.json()
                print("SCHEDULE keys:", list(data.keys()) if isinstance(data, dict) else type(data))
                return data if isinstance(data, dict) else {}
    except Exception as e:
        print("SCHEDULE ERROR:", e)
        return {}


# =========================
# Вспомогательная функция: получить данные недели (с кэшем в FSM)
# =========================

async def get_week_data(
    state: FSMContext,
    token: str,
    group_id: int,
    target_date: date,
) -> dict[int, list]:
    """
    Возвращает {weekday: [lessons]} для недели, содержащей target_date.
    Кэш хранится в FSM по ключу "sched_cache_{week_num}".
    """
    week_num = get_knrtu_week_number(target_date)
    cache_key = f"sched_cache_{week_num}"

    fsm_data = await state.get_data()
    if cache_key in fsm_data:
        return fsm_data[cache_key]

    api_resp = await fetch_schedule(token, group_id, week_num)
    days = parse_schedule_days(api_resp)

    await state.update_data({cache_key: days})
    return days


# =========================
# Вспомогательная: авторизация из профиля
# =========================

async def get_token_and_group(user_id: int):
    """Возвращает (token, group_id) или (None, None) при ошибке."""
    profile = await get_user_profile(user_id)
    if not profile:
        return None, None

    group_id = profile.get("group_id")
    login = profile.get("knrtu_login")
    raw_password = profile.get("knrtu_password_raw")

    if not group_id or not login or not raw_password:
        return None, group_id

    token = await check_knrtu_auth(login, raw_password)
    return token, group_id


# =========================
# HANDLER: открытие расписания
# =========================

@router.callback_query(F.data == "schedule")
async def cmd_schedule(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)

    if not profile:
        await callback.message.edit_text("❌ Профиль не найден. /start", reply_markup=kb.education)
        return

    group_id = profile.get("group_id")
    if not group_id:
        await callback.message.edit_text(
            "❌ Группа не определена. Пройдите регистрацию заново: /start",
            reply_markup=kb.education
        )
        return

    login = profile.get("knrtu_login")
    raw_password = profile.get("knrtu_password_raw")
    if not login or not raw_password:
        await callback.message.edit_text(
            "⚠️ Нет данных для авторизации. Пройдите регистрацию заново: /start",
            reply_markup=kb.education
        )
        return

    loading_msg = await callback.message.edit_text("⏳ Загружаю расписание...")

    token = await check_knrtu_auth(login, raw_password)
    if not token:
        await loading_msg.edit_text(
            "⚠️ Не удалось авторизоваться в КНИТУ.\n"
            "Возможно, пароль изменился. Пройдите регистрацию заново: /start",
            reply_markup=kb.education
        )
        return

    # Сохраняем токен и group_id в FSM для использования при листании
    await state.update_data(sched_token=token, sched_group_id=group_id)

    today = date.today()
    week_num = get_knrtu_week_number(today)
    days = await get_week_data(state, token, group_id, today)

    text = format_day(days, today, week_num)
    nav_kb = get_nav_kb(today)

    await loading_msg.edit_text(text, reply_markup=nav_kb, parse_mode='HTML')

    await log_activity(callback.from_user.id, "schedule")


# =========================
# HANDLER: листание по дням (callback sched_day_ДД.ММ.ГГГГ)
# =========================

@router.callback_query(F.data.startswith("sched_day_"))
async def sched_navigate_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    date_str = callback.data.replace("sched_day_", "")
    try:
        target_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        await callback.answer("❌ Неверный формат даты", show_alert=True)
        return

    fsm_data = await state.get_data()
    token = fsm_data.get("sched_token")
    group_id = fsm_data.get("sched_group_id")

    # Если токен/группа не в FSM — перезагружаем (например после перезапуска бота)
    if not token or not group_id:
        token, group_id = await get_token_and_group(callback.from_user.id)
        if not token:
            await callback.message.edit_text(
                "⚠️ Сессия устарела. Откройте расписание заново.",
                reply_markup=kb.education
            )
            return
        await state.update_data(sched_token=token, sched_group_id=group_id)

    week_num = get_knrtu_week_number(target_date)
    days = await get_week_data(state, token, group_id, target_date)

    text = format_day(days, target_date, week_num)
    nav_kb = get_nav_kb(target_date)

    await callback.message.edit_text(text, reply_markup=nav_kb, parse_mode='HTML')


# =========================
# HANDLER: кнопка «Ввести дату»
# =========================

@router.callback_query(F.data == "sched_enter_date")
async def sched_enter_date_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ScheduleStates.waiting_date_input)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="sched_cancel_date_input")]
    ])

    await callback.message.edit_text(
        "📅 <b>Введите дату</b> в формате <code>ДД.ММ.ГГГГ</code>\n\n"
        "<i>Например: 15.04.2026</i>",
        reply_markup=cancel_kb,
        parse_mode='HTML'
    )


@router.callback_query(F.data == "sched_cancel_date_input")
async def sched_cancel_date_input(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)   # Выходим из ожидания, но не очищаем кэш
    await callback.answer()

    # Возвращаем к сегодняшнему дню
    fsm_data = await state.get_data()
    token = fsm_data.get("sched_token")
    group_id = fsm_data.get("sched_group_id")

    if not token or not group_id:
        await callback.message.edit_text("⚠️ Откройте расписание заново.", reply_markup=kb.education)
        return

    today = date.today()
    week_num = get_knrtu_week_number(today)
    days = await get_week_data(state, token, group_id, today)

    text = format_day(days, today, week_num)
    await callback.message.edit_text(text, reply_markup=get_nav_kb(today), parse_mode='HTML')


# =========================
# HANDLER: получение введённой даты
# =========================

@router.message(ScheduleStates.waiting_date_input, F.text)
async def sched_receive_date_input(message: Message, state: FSMContext):
    raw = message.text.strip()

    try:
        target_date = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введите дату как <code>ДД.ММ.ГГГГ</code>, например <code>15.04.2026</code>",
            parse_mode='HTML'
        )
        return

    await state.set_state(None)

    fsm_data = await state.get_data()
    token = fsm_data.get("sched_token")
    group_id = fsm_data.get("sched_group_id")

    if not token or not group_id:
        token, group_id = await get_token_and_group(message.from_user.id)
        if not token:
            await message.answer(
                "⚠️ Сессия устарела. Откройте расписание через меню.",
                reply_markup=kb.education
            )
            return
        await state.update_data(sched_token=token, sched_group_id=group_id)

    loading = await message.answer("⏳ Загружаю...")

    week_num = get_knrtu_week_number(target_date)
    days = await get_week_data(state, token, group_id, target_date)

    text = format_day(days, target_date, week_num)
    nav_kb = get_nav_kb(target_date)

    await loading.edit_text(text, reply_markup=nav_kb, parse_mode='HTML')