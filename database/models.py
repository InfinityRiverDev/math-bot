import aiosqlite
from datetime import datetime

DB_PATH = 'bot-math_database.db'


async def db_start():
    """Создает таблицу пользователей при запуске бота"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT
            )
        """)
        await db.commit()


async def register_user(user_id: int, username: str):
    """
    Сохраняет пользователя или обновляет его username,
    если он изменился с момента последнего захода.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Пытаемся найти пользователя
        async with db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row is None:
            # Если пользователя нет — создаем новую запись
            await db.execute(
                "INSERT INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
                (user_id, username, now)
            )
            await db.commit()
            return True  # Новый пользователь

        # Если пользователь есть, но сменил ник — обновляем его
        elif row[0] != username:
            await db.execute(
                "UPDATE users SET username = ? WHERE user_id = ?",
                (username, user_id)
            )
            await db.commit()

        return False  # Пользователь уже был в базе


async def get_all_users():
    """Возвращает список всех ID пользователей из базы"""
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