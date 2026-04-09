"""
database/lectures_models.py
Модели для работы с лекциями в MongoDB.
"""

from bson import ObjectId
from database.mongo import db

subjects = db["subjects"]    # Предметы
lectures = db["lectures"]    # Лекции (PDF)


# =========================
# 📘 Предметы
# =========================

async def get_all_subjects() -> list:
    cursor = subjects.find({})
    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result


async def add_subject(name: str) -> str:
    result = await subjects.insert_one({"name": name})
    return str(result.inserted_id)


async def delete_subject(subject_id: str):
    await subjects.delete_one({"_id": ObjectId(subject_id)})
    # Удаляем все лекции этого предмета
    await lectures.delete_many({"subject_id": subject_id})


# =========================
# 📄 Лекции
# =========================

async def get_lectures_by_subject(subject_id: str) -> list:
    cursor = lectures.find({"subject_id": subject_id})
    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result


async def get_lecture_by_id(lecture_id: str):
    doc = await lectures.find_one({"_id": ObjectId(lecture_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def add_lecture(subject_id: str, title: str, file_id: str) -> str:
    result = await lectures.insert_one({
        "subject_id": subject_id,
        "title": title,
        "file_id": file_id
    })
    return str(result.inserted_id)


async def delete_lecture(lecture_id: str):
    await lectures.delete_one({"_id": ObjectId(lecture_id)})