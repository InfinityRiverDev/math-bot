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

router = Router()

INSTITUTES = ["ИУАИТ", "ИХТИ", "ИУИ", "ИП", "ИНХН", "ИХНМ", "ИТЛПМД", "ИППБ"]


# ========================
# FSM регистрации
# ========================

class RegStates(StatesGroup):
    first_name = State()
    last_name = State()
    institute = State()
    group = State()
    knrtu_login = State()
    knrtu_password = State()
    policy = State()
    confirm = State()


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
    admin_id = None
    try:
        import os
        admin_id = int(os.getenv("ADMIN_ID", 0))
    except:
        pass

    already = await is_registered(user_id)

    if already:
        # Уже зарегистрирован — показываем главное меню
        await state.clear()
        is_admin = (user_id == admin_id)
        await message.answer(
            'Привет! Я математический бот 🤖\nВыбери что хочешь сделать:',
            reply_markup=kb.get_start_kb(is_admin),
            parse_mode='HTML'
        )
    else:
        # Первый раз — запускаем регистрацию
        await state.clear()
        await state.set_state(RegStates.first_name)
        await message.answer(
            "👋 <b>Добро пожаловать!</b>\n\n"
            "Прежде чем начать, нужно пройти быструю регистрацию.\n\n"
            "<b>Шаг 1 из 6</b> — Введите ваше <b>имя</b>:",
            parse_mode='HTML'
        )


# ========================
# Шаг 1 — Имя
# ========================

@router.message(RegStates.first_name, F.text)
async def reg_first_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Попробуйте снова:")
        return
    await state.update_data(first_name=name)
    await message.answer(
        f"Вы ввели имя: <b>{name}</b>",
        reply_markup=get_check_kb("first_name"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_first_name", RegStates.first_name)
async def check_ok_first_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.last_name)
    await callback.message.edit_text(
        "<b>Шаг 2 из 6</b> — Введите вашу <b>фамилию</b>:",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_first_name", RegStates.first_name)
async def check_edit_first_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 1 из 6</b> — Введите ваше <b>имя</b> снова:",
        parse_mode='HTML'
    )


# ========================
# Шаг 2 — Фамилия
# ========================

@router.message(RegStates.last_name, F.text)
async def reg_last_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Фамилия слишком короткая. Попробуйте снова:")
        return
    await state.update_data(last_name=name)
    await message.answer(
        f"Вы ввели фамилию: <b>{name}</b>",
        reply_markup=get_check_kb("last_name"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_last_name", RegStates.last_name)
async def check_ok_last_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.institute)
    await callback.message.edit_text(
        "<b>Шаг 3 из 6</b> — Выберите ваш <b>институт</b>:",
        reply_markup=get_institute_kb(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_last_name", RegStates.last_name)
async def check_edit_last_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 2 из 6</b> — Введите вашу <b>фамилию</b> снова:",
        parse_mode='HTML'
    )


# ========================
# Шаг 3 — Институт
# ========================

@router.callback_query(F.data.startswith("inst_"), RegStates.institute)
async def reg_institute(callback: CallbackQuery, state: FSMContext):
    inst = callback.data.replace("inst_", "")
    await state.update_data(institute=inst)
    await callback.answer()
    await callback.message.edit_text(
        f"Вы выбрали институт: <b>{inst}</b>",
        reply_markup=get_check_kb("institute"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_institute", RegStates.institute)
async def check_ok_institute(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.group)
    await callback.message.edit_text(
        "<b>Шаг 4 из 6</b> — Введите ваш <b>номер группы</b>\n"
        "<i>Например: 151-24</i>",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_institute", RegStates.institute)
async def check_edit_institute(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 3 из 6</b> — Выберите ваш <b>институт</b> снова:",
        reply_markup=get_institute_kb(),
        parse_mode='HTML'
    )


# ========================
# Шаг 4 — Группа
# ========================

@router.message(RegStates.group, F.text)
async def reg_group(message: Message, state: FSMContext):
    group = message.text.strip()
    if not re.match(r'^\d{3}-\d{2}$', group):
        await message.answer(
            "❌ Неверный формат. Введите номер группы в формате <code>151-24</code>:",
            parse_mode='HTML'
        )
        return
    await state.update_data(group=group)
    await message.answer(
        f"Вы ввели группу: <b>{group}</b>",
        reply_markup=get_check_kb("group"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_group", RegStates.group)
async def check_ok_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.knrtu_login)
    await callback.message.edit_text(
        "<b>Шаг 5 из 6</b> — Введите ваш <b>логин от КНИТУ ONE</b>:",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_group", RegStates.group)
async def check_edit_group(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 4 из 6</b> — Введите ваш <b>номер группы</b> снова\n"
        "<i>Например: 151-24</i>",
        parse_mode='HTML'
    )


# ========================
# Шаг 5 — Логин КНИТУ ONE
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
        "<b>Шаг 6 из 6</b> — Введите ваш <b>пароль от КНИТУ ONE</b>:\n\n"
        "<i>⚠️ Пароль будет сохранён в зашифрованном виде.\nОн используется только для авторизации и не передаётся третьим лицам</i>",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_edit_knrtu_login", RegStates.knrtu_login)
async def check_edit_login(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "<b>Шаг 5 из 6</b> — Введите ваш <b>логин от КНИТУ ONE</b> снова:",
        parse_mode='HTML'
    )


# ========================
# Шаг 6 — Пароль КНИТУ ONE
# ========================

@router.message(RegStates.knrtu_password, F.text)
async def reg_password(message: Message, state: FSMContext):
    password = message.text.strip()
    if len(password) < 4:
        await message.answer("❌ Пароль слишком короткий. Попробуйте снова:")
        return

    # Удаляем сообщение с паролем из чата для безопасности
    try:
        await message.delete()
    except:
        pass

    await state.update_data(knrtu_password=password)
    await message.answer(
        f"Пароль введён: {password}",
        reply_markup=get_check_kb("knrtu_password"),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_ok_knrtu_password", RegStates.knrtu_password)
async def check_ok_password(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegStates.policy)
    await callback.message.edit_text(
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
        "📝 <b>Проверьте введённые данные:</b>\n\n"
        f"👤 <b>Имя:</b> {data.get('first_name')}\n"
        f"👤 <b>Фамилия:</b> {data.get('last_name')}\n"
        f"🏛 <b>Институт:</b> {data.get('institute')}\n"
        f"📚 <b>Группа:</b> {data.get('group')}\n"
        f"🔑 <b>Логин КНИТУ ONE:</b> {data.get('knrtu_login')}\n"
        f"🔒 <b>Пароль:</b> {data.get('knrtu_password')}\n\n"
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
    await state.set_state(RegStates.first_name)
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

    import os
    try:
        admin_id = int(os.getenv("ADMIN_ID", 0))
    except:
        admin_id = 0
    is_admin = (user_id == admin_id)

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
