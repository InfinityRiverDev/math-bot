"""
database/todo_models.py
Модели для To-Do списка.
"""

from datetime import datetime
from bson import ObjectId
from database.mongo import db

todos = db["todos"]


# =========================
# 📋 Получить задачи пользователя
# =========================
async def get_todos(user_id: int, filter_mode: str = "all") -> list:
    """
    filter_mode: "all" | "active" | "done"
    Возвращает список задач, отсортированных по приоритету и дате.
    """
    query = {"user_id": user_id}

    if filter_mode == "active":
        query["done"] = False
    elif filter_mode == "done":
        query["done"] = True

    cursor = todos.find(query).sort([
        ("priority", -1),       # 3=🔴 > 2=🟡 > 1=🟢
        ("created_at", 1)
    ])

    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result


# =========================
# ➕ Добавить задачу
# =========================
async def add_todo(
    user_id: int,
    text: str,
    priority: int = 2,
    deadline: str = None,   # ISO строка или None
) -> str:
    result = await todos.insert_one({
        "user_id": user_id,
        "text": text,
        "done": False,
        "priority": priority,       # 1=🟢 2=🟡 3=🔴
        "deadline": deadline,
        "created_at": datetime.now().isoformat(),
    })
    return str(result.inserted_id)


# =========================
# ✅ Переключить выполнение
# =========================
async def toggle_todo(todo_id: str):
    doc = await todos.find_one({"_id": ObjectId(todo_id)})
    if not doc:
        return
    await todos.update_one(
        {"_id": ObjectId(todo_id)},
        {"$set": {
            "done": not doc["done"],
            "done_at": datetime.now().isoformat() if not doc["done"] else None
        }}
    )


# =========================
# 🔄 Сменить приоритет (циклично: 1→2→3→1)
# =========================
async def cycle_priority(todo_id: str):
    doc = await todos.find_one({"_id": ObjectId(todo_id)})
    if not doc:
        return
    new_priority = (doc["priority"] % 3) + 1
    await todos.update_one(
        {"_id": ObjectId(todo_id)},
        {"$set": {"priority": new_priority}}
    )


# =========================
# ✏️ Редактировать текст
# =========================
async def edit_todo_text(todo_id: str, new_text: str):
    await todos.update_one(
        {"_id": ObjectId(todo_id)},
        {"$set": {"text": new_text, "edited_at": datetime.now().isoformat()}}
    )


# =========================
# 🗑 Удалить задачу
# =========================
async def delete_todo(todo_id: str):
    await todos.delete_one({"_id": ObjectId(todo_id)})


# =========================
# 🧹 Удалить все выполненные
# =========================
async def clear_done(user_id: int):
    await todos.delete_many({"user_id": user_id, "done": True})


# =========================
# 📊 Статистика
# =========================
async def get_stats(user_id: int) -> dict:
    total = await todos.count_documents({"user_id": user_id})
    done  = await todos.count_documents({"user_id": user_id, "done": True})
    return {"total": total, "done": done, "active": total - done}


# =========================
# 🔍 Получить одну задачу
# =========================
async def get_todo(todo_id: str) -> dict | None:
    doc = await todos.find_one({"_id": ObjectId(todo_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
