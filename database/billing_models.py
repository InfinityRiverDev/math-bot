"""
database/billing_models.py
Модели для кошелька, тарифов, подписок, промокодов и платежей.
"""

from datetime import datetime, timedelta
from bson import ObjectId
from database.mongo import db

wallets      = db["wallets"]       # Кошельки пользователей
plans        = db["plans"]         # Тарифы (создаются админом)
subscriptions = db["subscriptions"] # Активные подписки
promo_codes  = db["promo_codes"]   # Промокоды
payments     = db["payments"]      # История платежей (ЮKassa)


# ===========================
# 💰 Кошелёк
# ===========================

async def get_wallet(user_id: int) -> dict:
    """Возвращает кошелёк пользователя, создаёт при отсутствии."""
    doc = await wallets.find_one({"user_id": user_id})
    if not doc:
        await wallets.insert_one({"user_id": user_id, "balance": 0})
        doc = await wallets.find_one({"user_id": user_id})
    doc["_id"] = str(doc["_id"])
    return doc


async def get_balance(user_id: int) -> float:
    wallet = await get_wallet(user_id)
    return wallet.get("balance", 0)


async def top_up_balance(user_id: int, amount: float):
    """Зачисляет amount на кошелёк."""
    await wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        upsert=True
    )


async def deduct_balance(user_id: int, amount: float) -> bool:
    """Списывает amount. Возвращает False если недостаточно средств."""
    wallet = await get_wallet(user_id)
    if wallet.get("balance", 0) < amount:
        return False
    await wallets.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": -amount}}
    )
    return True


# ===========================
# 📦 Тарифы
# ===========================

async def get_all_plans() -> list:
    cursor = plans.find({"active": True})
    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result


async def get_plan(plan_id: str) -> dict | None:
    doc = await plans.find_one({"_id": ObjectId(plan_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def create_plan(name: str, price: float, duration_days: int, description: str = "") -> str:
    result = await plans.insert_one({
        "name": name,
        "price": price,
        "duration_days": duration_days,
        "description": description,
        "active": True,
        "created_at": datetime.now().isoformat()
    })
    return str(result.inserted_id)


async def update_plan(plan_id: str, **kwargs):
    await plans.update_one(
        {"_id": ObjectId(plan_id)},
        {"$set": kwargs}
    )


async def delete_plan(plan_id: str):
    """Мягкое удаление — скрывает тариф."""
    await plans.update_one({"_id": ObjectId(plan_id)}, {"$set": {"active": False}})


# ===========================
# 🎟 Промокоды
# ===========================

async def get_all_promo_codes() -> list:
    cursor = promo_codes.find({})
    result = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        result.append(doc)
    return result


async def get_promo_by_code(code: str) -> dict | None:
    doc = await promo_codes.find_one({"code": code.upper(), "active": True})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def create_promo(code: str, discount_percent: int, max_uses: int = 0) -> str:
    """
    max_uses=0 — неограниченное количество использований.
    """
    result = await promo_codes.insert_one({
        "code": code.upper(),
        "discount_percent": discount_percent,
        "max_uses": max_uses,
        "uses_count": 0,
        "active": True,
        "created_at": datetime.now().isoformat()
    })
    return str(result.inserted_id)


async def delete_promo(promo_id: str):
    """Полное удаление промокода из базы."""
    await promo_codes.delete_one({"_id": ObjectId(promo_id)})


async def use_promo(code: str):
    """Увеличивает счётчик использований; деактивирует если исчерпан."""
    doc = await promo_codes.find_one({"code": code.upper()})
    if not doc:
        return
    new_count = doc.get("uses_count", 0) + 1
    max_uses = doc.get("max_uses", 0)
    update = {"$set": {"uses_count": new_count}}
    if max_uses > 0 and new_count >= max_uses:
        update["$set"]["active"] = False
    await promo_codes.update_one({"_id": doc["_id"]}, update)


# ===========================
# 🔑 Подписки
# ===========================

async def get_active_subscription(user_id: int) -> dict | None:
    now = datetime.now().isoformat()
    doc = await subscriptions.find_one({
        "user_id": user_id,
        "expires_at": {"$gt": now}
    })
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def has_active_subscription(user_id: int) -> bool:
    sub = await get_active_subscription(user_id)
    return sub is not None


async def activate_subscription(user_id: int, plan_id: str, duration_days: int, plan_name: str):
    """Активирует подписку (продлевает если уже есть активная)."""
    existing = await get_active_subscription(user_id)

    if existing:
        # Продлеваем от текущего окончания
        current_expires = datetime.fromisoformat(existing["expires_at"])
        new_expires = current_expires + timedelta(days=duration_days)
    else:
        new_expires = datetime.now() + timedelta(days=duration_days)

    await subscriptions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "plan_id": plan_id,
            "plan_name": plan_name,
            "activated_at": datetime.now().isoformat(),
            "expires_at": new_expires.isoformat()
        }},
        upsert=True
    )


# ===========================
# 📋 Платежи (история)
# ===========================

async def save_payment(user_id: int, payment_id: str, amount: float, status: str):
    await payments.insert_one({
        "user_id": user_id,
        "payment_id": payment_id,
        "amount": amount,
        "status": status,
        "created_at": datetime.now().isoformat()
    })


async def get_payment_by_id(payment_id: str) -> dict | None:
    doc = await payments.find_one({"payment_id": payment_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_payment_status(payment_id: str, status: str):
    await payments.update_one(
        {"payment_id": payment_id},
        {"$set": {"status": status, "updated_at": datetime.now().isoformat()}}
    )