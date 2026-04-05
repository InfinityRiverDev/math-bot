import hashlib
import os
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from database.models import get_user_profile, delete_user_profile, check_password
import keyboards.user_kb as kb

router = Router()


class ProfileStates(StatesGroup):
    waiting_delete_password = State()


# ========================
# Клавиатуры
# ========================

def get_profile_actions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить данные", callback_data="profile_edit")],
        [InlineKeyboardButton(text="🗑 Удалить профиль", callback_data="profile_delete")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ])


def get_delete_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить", callback_data="profile_delete_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="profile_view")]
    ])


# ========================
# Просмотр профиля
# ========================

@router.callback_query(F.data == "profile_view")
@router.callback_query(F.data == "print")  # кнопка "Данные пользователя" в user_kb.py
async def view_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)

    if not profile:
        await callback.message.edit_text(
            "❌ Профиль не найден. Пройдите регистрацию: /start",
            parse_mode='HTML'
        )
        return

    await callback.message.edit_text(
        "👤 <b>Данные пользователя</b>\n\n"
        f"📝 <b>Имя:</b> {profile['first_name']}\n"
        f"📝 <b>Фамилия:</b> {profile['last_name']}\n"
        f"🏛 <b>Институт:</b> {profile['institute']}\n"
        f"📚 <b>Группа:</b> {profile['group_number']}\n"
        f"🔑 <b>Логин КНИТУ ONE:</b> {profile['knrtu_login']}\n"
        f"🔒 <b>Пароль:</b> ••••••••\n"
        f"📅 <b>Дата регистрации:</b> {profile['registered_at']}\n",
        reply_markup=get_profile_actions_kb(),
        parse_mode='HTML'
    )


# ========================
# Изменить данные — перезапуск регистрации
# ========================

@router.callback_query(F.data == "profile_edit")
async def profile_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    # Импортируем состояния регистрации и запускаем заново
    from handlers.registration import RegStates
    await state.set_state(RegStates.first_name)
    await callback.message.edit_text(
        "🔄 <b>Изменение данных</b>\n\n"
        "Пройдите регистрацию заново — новые данные заменят старые.\n\n"
        "<b>Шаг 1 из 6</b> — Введите ваше <b>имя</b>:",
        parse_mode='HTML'
    )


# ========================
# Удалить профиль — подтверждение
# ========================

@router.callback_query(F.data == "profile_delete")
async def profile_delete(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    profile = await get_user_profile(user_id)

    name = f"{profile['first_name']} {profile['last_name']}" if profile else "пользователь"

    await callback.message.edit_text(
        f"⚠️ <b>Вы действительно хотите удалить профиль?</b>\n\n"
        f"👤 <b>{name}</b>\n\n"
        "Все ваши данные будут безвозвратно удалены.",
        reply_markup=get_delete_confirm_kb(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "profile_delete_confirm")
async def profile_delete_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProfileStates.waiting_delete_password)
    await callback.message.edit_text(
        "🔒 <b>Введите пароль от КНИТУ ONE</b> для подтверждения удаления профиля:",
        parse_mode='HTML'
    )


# ========================
# Удалить профиль — проверка пароля
# ========================

@router.message(ProfileStates.waiting_delete_password, F.text)
async def profile_delete_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    password = message.text.strip()

    # Удаляем сообщение с паролем для безопасности
    try:
        await message.delete()
    except:
        pass

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    is_correct = await check_password(user_id, password_hash)

    if not is_correct:
        await message.answer(
            "❌ <b>Неверный пароль.</b>\n\n"
            "Попробуйте снова или нажмите /start для возврата в меню.",
            parse_mode='HTML'
        )
        return

    await delete_user_profile(user_id)
    await state.clear()

    await message.answer(
        "✅ <b>Профиль успешно удалён.</b>\n\n"
        "Все ваши данные были удалены из системы.\n"
        "Для повторной регистрации нажмите /start",
        parse_mode='HTML'
    )
