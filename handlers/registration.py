import hashlib
import re
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.models import is_registered, register_user_full
import keyboards.user_kb as kb
from services.links import federal_law_152_fz
from handlers.admin import ADMIN_IDS

router = Router()

INSTITUTES = ["ИУАИТ", "ИХТИ", "ИУИ", "ИП", "ИНХН", "ИХНМ", "ИТЛПМД", "ИППБ"]


# ========================
# FSM регистрации
# ========================

class RegStates(StatesGroup):
    knrtu_login = State()
    knrtu_password = State()
    policy = State()
    confirm = State()


import aiohttp
#проверка пароля и логина
async def check_knrtu_auth(login: str, password: str) -> bool:
    url = "https://rest.kstu.ru/restapi/login/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "username": login,
                    "password": password
                },
                headers={
                    "accept": "*/*",
                    "accept-language": "ru,en;q=0.9",
                    "content-type": "application/json",
                    "Referer": "https://one.kstu.ru/",
                    "origin": "https://one.kstu.ru"
                }
            ) as resp:

                data = await resp.json()
                print("KSTU RESPONSE:", data)

                token = data.get("token") or data.get("access")
                return token

    except Exception as e:
        print("KSTU AUTH ERROR:", e)
        return False
    

async def get_knrtu_profile(token: str):
    url = "https://rest.kstu.ru/restapi/my-profile/"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    "authorization": f"Token {token}"
                }
            ) as resp:

                data = await resp.json()
                print("PROFILE DATA:", data)

                first_name = data.get("name")
                last_name = data.get("surname")
                group = data.get("role", {}).get("student_desc", {}).get("group")

                return first_name, last_name, group

    except Exception as e:
        print("PROFILE ERROR:", e)
        return None, None, None
    
def get_institute_from_group(group: str) -> str:
    if not group:
        return "Неизвестно"

    try:
        index = int(group[0]) - 1
        return INSTITUTES[index]
    except:
        return "Неизвестно"

# ========================
# Клавиатуры
# ========================

def get_institute_kb():
    buttons = []
    row = []
    for i, inst in enumerate(INSTITUTES):
        row.append(InlineKeyboardButton(text=inst, callback_data=f"inst_{inst}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_check_kb(field: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Верно, продолжить", callback_data=f"check_ok_{field}"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"check_edit_{field}")
        ]
    ])


def get_policy_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласен", callback_data="policy_agree")],
        [InlineKeyboardButton(text="❌ Не согласен", callback_data="policy_disagree")]
    ])


def get_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="reg_confirm")],
        [InlineKeyboardButton(text="✏️ Изменить данные", callback_data="reg_edit")]
    ])


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ========================
# /start — точка входа
# ========================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    await message.answer_sticker(
        sticker="CAACAgIAAxkBAAFGiSNp0wHNqj0qnak00qEBwayIjgz6sQACjqIAAnjAkUoNk2wSUaJW9jsE"
    )

    already = await is_registered(user_id)

    if already:
        # Уже зарегистрирован — показываем главное меню
        await state.clear()
        is_admin = user_id in ADMIN_IDS
        await message.answer(
            'Привет! Я математический бот 🤖\nВыбери что хочешь сделать:',
            reply_markup=kb.get_start_kb(is_admin),
            parse_mode='HTML'
        )
    else:
        # Первый раз — запускаем регистрацию
        await state.clear()
        await state.set_state(RegStates.knrtu_login)

        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Введите ваш <b>логин от КНИТУ ONE</b>:",
            parse_mode='HTML'
        )


# ========================
# Шаг 1 — Логин КНИТУ ONE
# ========================

@router.message(RegStates.knrtu_login, F.text)
async def reg_login(message: Message, state: FSMContext):
    login = message.text.strip()
    if len(login) < 3:
        await message.answer("❌ Логин слишком короткий. Попробуйте снова:")
        return
    await state.update_data(knrtu_login=login)
    await message.answer(
        f"Вы ввели логин: <b>{login}</b>",
        reply_markup=get_check_kb("knrtu_login"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_knrtu_login", RegStates.knrtu_login)
async def check_ok_login(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.knrtu_password)
    await callback.message.edit_text(
        "Введите ваш <b>пароль от КНИТУ ONE</b>:\n\n"
        "<i>⚠️ Пароль будет сохранён в зашифрованном виде.\nОн используется только для авторизации и не передаётся третьим лицам</i>",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_knrtu_login", RegStates.knrtu_login)
async def check_edit_login(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "Введите ваш <b>логин от КНИТУ ONE</b> снова:",
        parse_mode='HTML'
    )


# ========================
# Шаг 6 — Пароль КНИТУ ONE
# ========================

@router.message(RegStates.knrtu_password, F.text)
async def reg_password(message: Message, state: FSMContext):
    password = message.text.strip()

    if len(password) < 4:
        await message.answer("❌ Пароль слишком короткий.")
        return

    data = await state.get_data()
    login = data.get("knrtu_login")

    msg = await message.answer("🔐 Проверяю данные КНИТУ...")

    token = await check_knrtu_auth(login, password)

    if not token:
        await msg.delete()
        await message.answer_sticker(
            sticker="CAACAgIAAxkBAAFGiS9p0wKb1Ara3VWQRrIKk8YfMYmKZgACZJcAA-WQSimWYJy9_vw3OwQ"
        )
        await message.answer("❌ Неверный логин или пароль. \nПопробуйте снова:")
        return

    await msg.edit_text("🔍 Ищу вашу группу...")

    first_name, last_name, group = await get_knrtu_profile(token)

    if not group:
        await msg.edit_text("❌ Не удалось получить данные профиля.")
        return

    institute = get_institute_from_group(group)

    # удаляем пароль из чата
    try:
        await message.delete()
    except:
        pass

    # сохраняем всё
    await state.update_data(
        knrtu_password=password,
        group=group,
        first_name=first_name,
        last_name=last_name,
        institute=institute
    )

    # дальше сразу подтверждение
    await state.set_state(RegStates.policy)

    await message.answer(
        "📋 <b>Политика обработки персональных данных.</b>\n\n"
        "Нажимая «Согласен», вы даёте согласие на обработку ваших персональных данных "
        f"в соответствии с {federal_law_152_fz} "
        "на условиях и для целей, определенных политикой конфиденциальности.\n\n"
        "Данные используются исключительно для идентификации в системе бота.",
        reply_markup=get_policy_kb(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_knrtu_password", RegStates.knrtu_password)
async def check_edit_password(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 6 из 6</b> — Введите ваш <b>пароль от КНИТУ ONE</b> снова:\n\n"
        "<i>⚠️ Пароль будет сохранён в зашифрованном виде</i>",
        parse_mode='HTML'
    )


# ========================
# Политика — Согласен / Не согласен
# ========================

@router.callback_query(F.data == "policy_disagree", RegStates.policy)
async def policy_disagree(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Регистрация отменена.</b>\n\n"
        "Для повторной регистрации нажмите /start",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "policy_agree", RegStates.policy)
async def policy_agree(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(RegStates.confirm)
    data = await state.get_data()

    await callback.message.edit_text(
        "📝 <b>Проверьте данные:</b>\n\n"
        f"👤 {data.get('first_name')} {data.get('last_name')}\n"
        f"🏛 {data.get('institute')}\n"
        f"📚 {data.get('group')}\n"
        f"🔑 {data.get('knrtu_login')}\n\n"
        "Всё верно?",
        reply_markup=get_confirm_kb(),
        parse_mode='HTML'
    )


# ========================
# Подтверждение / Изменение
# ========================

@router.callback_query(F.data == "reg_edit", RegStates.confirm)
async def reg_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🔄 <b>Начинаем регистрацию заново.</b>\n\n"
        "<b>Шаг 1 из 6</b> — Введите ваше <b>имя</b>:",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "reg_confirm", RegStates.confirm)
async def reg_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    hashed_password = hash_password(data.get('knrtu_password', ''))

    await register_user_full(
        user_id=user_id,
        username=username,
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        institute=data.get('institute'),
        group=data.get('group'),
        knrtu_login=data.get('knrtu_login'),
        knrtu_password=hashed_password
    )

    await state.clear()

    from handlers.admin import ADMIN_IDS
    is_admin = user_id in ADMIN_IDS

    await callback.message.edit_text(
        "🎉 <b>Регистрация успешно завершена!</b>\n\n"
        f"Добро пожаловать, <b>{data.get('first_name')} {data.get('last_name')}</b>!\n\n"
        "Теперь вы можете пользоваться всеми функциями бота.",
        parse_mode='HTML'
    )

    await callback.message.answer(
        'Выбери что хочешь сделать:',
        reply_markup=kb.get_start_kb(is_admin),
        parse_mode='HTML'
    )
