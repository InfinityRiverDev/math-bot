# import aiosqlite
# from datetime import datetime
#
# DB_PATH = 'bot-math_database.db'
#
#
# async def db_start():
#     """Создает таблицы при запуске бота"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         # Старая таблица users (оставляем для совместимости)
#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 user_id INTEGER PRIMARY KEY,
#                 username TEXT,
#                 first_seen TEXT
#             )
#         """)
#         # Новая таблица с полными данными регистрации
#         await db.execute("""
#             CREATE TABLE IF NOT EXISTS user_profiles (
#                 user_id INTEGER PRIMARY KEY,
#                 username TEXT,
#                 first_name TEXT,
#                 last_name TEXT,
#                 institute TEXT,
#                 group_number TEXT,
#                 knrtu_login TEXT,
#                 knrtu_password TEXT,
#                 registered_at TEXT
#             )
#         """)
#         await db.commit()
#
#
# async def is_registered(user_id: int) -> bool:
#     """Проверяет, зарегистрирован ли пользователь"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#                 "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
#         ) as cursor:
#             row = await cursor.fetchone()
#             return row is not None
#
#
# async def register_user_full(
#         user_id: int,
#         username: str,
#         first_name: str,
#         last_name: str,
#         institute: str,
#         group: str,
#         knrtu_login: str,
#         knrtu_password: str
# ):
#     """Сохраняет полные данные пользователя после регистрации"""
#     now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     async with aiosqlite.connect(DB_PATH) as db:
#         await db.execute("""
#             INSERT OR REPLACE INTO user_profiles
#             (user_id, username, first_name, last_name, institute, group_number, knrtu_login, knrtu_password, registered_at)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, (user_id, username, first_name, last_name, institute, group, knrtu_login, knrtu_password, now))
#         # Также регистрируем в старой таблице users
#         async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
#             row = await cursor.fetchone()
#         if row is None:
#             await db.execute(
#                 "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
#                 (user_id, username, now)
#             )
#         await db.commit()
#
#
# async def get_user_profile(user_id: int) -> dict | None:
#     """Возвращает профиль пользователя"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute(
#                 "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
#         ) as cursor:
#             row = await cursor.fetchone()
#             if row is None:
#                 return None
#             return {
#                 "user_id": row[0],
#                 "username": row[1],
#                 "first_name": row[2],
#                 "last_name": row[3],
#                 "institute": row[4],
#                 "group_number": row[5],
#                 "knrtu_login": row[6],
#                 "registered_at": row[8]
#             }
#
#
# async def register_user(user_id: int, username: str):
#     """
#     Старая функция — оставляем для совместимости.
#     Сохраняет пользователя в таблицу users.
#     """
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)) as cursor:
#             row = await cursor.fetchone()
#
#         now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#
#         if row is None:
#             await db.execute(
#                 "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
#                 (user_id, username, now)
#             )
#             await db.commit()
#             return True
#         elif row[0] != username:
#             await db.execute(
#                 "UPDATE users SET username = ? WHERE user_id = ?",
#                 (username, user_id)
#             )
#             await db.commit()
#         return False
#
#
# async def get_all_users():
#     """Возвращает список всех ID пользователей"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute("SELECT user_id FROM users") as cursor:
#             rows = await cursor.fetchall()
#             return [row[0] for row in rows]
#
#
# async def count_users():
#     """Возвращает общее количество пользователей"""
#     async with aiosqlite.connect(DB_PATH) as db:
#         async with db.execute("SELECT COUNT(*) FROM users") as cursor:
#             row = await cursor.fetchone()
#             return row[0] if row else 0

import aiosqlite
from datetime import datetime

DB_PATH = 'bot-math_database.db'


async def db_start():
    """Создает таблицы при запуске бота"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Старая таблица users (оставляем для совместимости)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT
            )
        """)
        # Новая таблица с полными данными регистрации
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                institute TEXT,
                group_number TEXT,
                knrtu_login TEXT,
                knrtu_password TEXT,
                registered_at TEXT
            )
        """)
        await db.commit()


async def is_registered(user_id: int) -> bool:
    """Проверяет, зарегистрирован ли пользователь"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


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
    """Сохраняет полные данные пользователя после регистрации"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_id, username, first_name, last_name, institute, group_number, knrtu_login, knrtu_password, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, institute, group, knrtu_login, knrtu_password, now))
        # Также регистрируем в старой таблице users
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
                (user_id, username, now)
            )
        await db.commit()


async def get_user_profile(user_id: int) -> dict | None:
    """Возвращает профиль пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "institute": row[4],
                "group_number": row[5],
                "knrtu_login": row[6],
                "registered_at": row[8]
            }


async def delete_user_profile(user_id: int):
    """Удаляет профиль пользователя из обеих таблиц"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()


async def check_password(user_id: int, password_hash: str) -> bool:
    """Проверяет пароль пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                "SELECT knrtu_password FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return False
            return row[0] == password_hash


async def register_user(user_id: int, username: str):
    """
    Старая функция — оставляем для совместимости.
    Сохраняет пользователя в таблицу users.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
                (user_id, username, now)
            )
            await db.commit()
            return True
        elif row[0] != username:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?",
                (username, user_id)
            )
            await db.commit()
        return False


async def get_all_users():
    """Возвращает список всех ID пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def count_users():
    """Возвращает общее количество пользователей"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0