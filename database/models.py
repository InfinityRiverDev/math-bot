from datetime import datetime
from database.mongo import users


# =========================
# 👤 Регистрация (простая)
# =========================
async def register_user(user_id: int, username: str):
    await users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "username": username,
                "first_seen": datetime.now().isoformat(),
                "xp": 0,
                "subscription": False,
                "tutor_history": []
            }
        },
        upsert=True
    )


# =========================
# 📋 Проверка регистрации
# =========================
async def is_registered(user_id: int) -> bool:
    user = await users.find_one({"user_id": user_id})
    return user is not None


# =========================
# 🧾 Полная регистрация
# =========================
async def register_user_full(
    user_id: int,
    username: str,
    first_name: str,
    last_name: str,
    institute: str,
    group: str,
    knrtu_login: str,
    knrtu_password: str
):
    await users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "institute": institute,
                "group_number": group,
                "knrtu_login": knrtu_login,
                "knrtu_password": knrtu_password,
                "registered_at": datetime.now().isoformat()
            }
        },
        upsert=True
    )


# =========================
# 👤 Получить профиль
# =========================
async def get_user_profile(user_id: int):
    return await users.find_one({"user_id": user_id})


# =========================
# ❌ Удаление профиля
# =========================
async def delete_user_profile(user_id: int):
    await users.delete_one({"user_id": user_id})


# =========================
# 🔐 Проверка пароля
# =========================
async def check_password(user_id: int, password_hash: str) -> bool:
    user = await users.find_one({"user_id": user_id})
    if not user:
        return False
    return user.get("knrtu_password") == password_hash


# =========================
# 📊 Кол-во пользователей
# =========================
async def count_users():
    return await users.count_documents({})


# =========================
# 📢 Все пользователи
# =========================
async def get_all_users():
    cursor = users.find({}, {"user_id": 1})
    return [doc["user_id"] async for doc in cursor]


# =========================
# 🧠 История ИИ
# =========================
async def get_history(user_id: int):
    user = await users.find_one({"user_id": user_id})
    return user.get("tutor_history", []) if user else []


async def update_history(user_id: int, history: list):
    await users.update_one(
        {"user_id": user_id},
        {"$set": {"tutor_history": history}}
    )