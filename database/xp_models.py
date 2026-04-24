"""
database/xp_models.py

Система начисления XP.
Все операции атомарные через $inc — нет race condition.
"""

from datetime import datetime
from database.mongo import db, users

xp_log = db["xp_log"]   # лог начислений для истории


# =========================
# 🏆 Таблица XP за действия
# =========================
XP_REWARDS = {
    # ИИ-репетитор
    "tutor_message":        5,   # отправил сообщение репетитору
    "tutor_voice":          8,   # голосовой вопрос репетитору
    "tutor_image":          8,   # фото репетитору
    "tutor_document":       6,   # документ репетитору
    "practice_request":    10,   # запросил задачи для практики
    "art_generated":        5, 

    # Калькулятор
    "calc_text":            3,   # решил задачу текстом
    "calc_image":           5,   # решил задачу по фото
    "calc_voice":           5,   # решил задачу голосом

    # Образование
    "lecture_downloaded":   4,   # скачал лекцию
    "schedule_opened":      2,   # открыл расписание

    # Фокус — Помодоро
    "pomodoro_started":     3,   # запустил помодоро
    "pomodoro_completed":  20,   # завершил рабочий цикл помодоро
    "pomodoro_5cycles":    50,   # завершил 5 циклов в одну сессию (бонус)

    # Фокус — To-Do
    "todo_added":           2,   # добавил задачу
    "todo_completed":       8,   # отметил задачу выполненной
    "todo_5_completed":    25,   # выполнил 5 задач (бонус)

    # Музыка
    "music_downloaded":     3,   # скачал трек

    # Посещаемость
    "attendance_marked":   15,   # автоотметка на паре

    # Регистрация
    "registration":        30,   # первичная регистрация

    # пополнил кошелёк
    "wallet_topup":        10,
}

# Уровни (XP → название)
LEVELS = [
    (0,    "🌱 Новичок"),
    (50,   "📘 Студент"),
    (150,  "✏️ Практик"),
    (300,  "🧮 Математик"),
    (600,  "🎓 Знаток"),
    (1000, "🏆 Профессор"),
    (2000, "🌟 Легенда"),
]


def get_level(xp: int) -> tuple[str, int, int]:
    """
    Возвращает (название_уровня, xp_до_следующего, номер_уровня).
    """
    current_level_name = LEVELS[0][1]
    current_idx = 0

    for i, (threshold, name) in enumerate(LEVELS):
        if xp >= threshold:
            current_level_name = name
            current_idx = i

    next_threshold = LEVELS[current_idx + 1][0] if current_idx + 1 < len(LEVELS) else None
    xp_to_next = (next_threshold - xp) if next_threshold else 0

    return current_level_name, xp_to_next, current_idx


def xp_progress_bar(xp: int, length: int = 8) -> str:
    """Прогресс-бар к следующему уровню."""
    _, _, idx = get_level(xp)
    if idx + 1 >= len(LEVELS):
        return "🌟" * length  # макс уровень

    current_threshold = LEVELS[idx][0]
    next_threshold    = LEVELS[idx + 1][0]
    span   = next_threshold - current_threshold
    filled = int(length * (xp - current_threshold) / span) if span else length
    filled = max(0, min(length, filled))
    return "🟦" * filled + "⬜" * (length - filled)


# =========================
# ➕ Начислить XP
# =========================
async def award_xp(user_id: int, action: str) -> dict | None:
    """
    Начисляет XP за действие.
    Возвращает dict с инфой о новом уровне если уровень повысился, иначе None.
    """
    amount = XP_REWARDS.get(action, 0)
    if amount == 0:
        return None

    # Читаем текущий XP
    user = await users.find_one({"user_id": user_id}, {"xp": 1})
    old_xp = (user or {}).get("xp", 0)

    # Атомарное начисление
    await users.update_one(
        {"user_id": user_id},
        {"$inc": {"xp": amount}},
        upsert=True
    )

    new_xp = old_xp + amount

    # Лог
    await xp_log.insert_one({
        "user_id": user_id,
        "action": action,
        "amount": amount,
        "xp_after": new_xp,
        "ts": datetime.now().isoformat()
    })

    # Проверяем смену уровня
    old_level, _, _ = get_level(old_xp)
    new_level, xp_to_next, _ = get_level(new_xp)

    if new_level != old_level:
        return {
            "leveled_up": True,
            "new_level": new_level,
            "xp": new_xp,
            "xp_to_next": xp_to_next,
        }
    return None


# =========================
# 📊 Получить XP профиль
# =========================
async def get_xp_profile(user_id: int) -> dict:
    user = await users.find_one({"user_id": user_id}, {"xp": 1})
    xp = (user or {}).get("xp", 0)
    level_name, xp_to_next, level_idx = get_level(xp)
    bar = xp_progress_bar(xp)
    return {
        "xp": xp,
        "level": level_name,
        "level_idx": level_idx,
        "xp_to_next": xp_to_next,
        "bar": bar,
        "max_level": level_idx + 1 >= len(LEVELS),
    }


# =========================
# 📜 Получить историю XP
# =========================
async def get_xp_history(user_id: int, limit: int = 10) -> list:
    cursor = xp_log.find(
        {"user_id": user_id}
    ).sort("ts", -1).limit(limit)

    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result
