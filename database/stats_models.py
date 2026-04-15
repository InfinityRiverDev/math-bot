"""
database/stats_models.py

Слой данных для статистики.

Логирование активности:
    from database.stats_models import log_activity
    await log_activity(user_id, "tutor")   # вызывай из хэндлеров

Категории action:
    tutor, practice, calc, pomodoro, music, todo,
    lecture, schedule, attendance
"""

from datetime import datetime, timedelta
from database.mongo import db
from database.billing_models import plans, subscriptions, payments, promo_codes, wallets

activity_log = db["activity_log"]  # {user_id, action, ts}
users = db["users"]


# =========================
# 📝 Логирование активности
# =========================
async def log_activity(user_id: int, action: str):
    """Вызывай из каждого хэндлера — одна строка."""
    await activity_log.insert_one({
        "user_id": user_id,
        "action": action,
        "ts": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "month": datetime.now().strftime("%Y-%m"),
    })


# =========================
# 👥 Пользователи
# =========================
async def stats_users() -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    week_ago = (now - timedelta(days=7)).isoformat()

    total = await users.count_documents({})
    with_sub = await subscriptions.count_documents({"expires_at": {"$gt": now.isoformat()}})
    new_today = await users.count_documents({"first_seen": {"$gte": today}})
    new_month = await users.count_documents({"first_seen": {"$gte": month}})
    new_week = await users.count_documents({"first_seen": {"$gte": week_ago}})

    return {
        "total": total,
        "with_sub": with_sub,
        "no_sub": total - with_sub,
        "new_today": new_today,
        "new_week": new_week,
        "new_month": new_month,
    }


# =========================
# 💳 Финансы
# =========================
async def stats_finance() -> dict:
    now = datetime.now()
    month = now.strftime("%Y-%m")
    today = now.strftime("%Y-%m-%d")

    # Все успешные платежи
    all_payments = []
    async for p in payments.find({"status": "succeeded"}):
        all_payments.append(p)

    total_revenue = sum(p.get("amount", 0) for p in all_payments)
    month_revenue = sum(
        p.get("amount", 0) for p in all_payments
        if p.get("created_at", "").startswith(month)
    )
    today_revenue = sum(
        p.get("amount", 0) for p in all_payments
        if p.get("created_at", "").startswith(today)
    )
    payment_count = len(all_payments)

    # Подписки по тарифам
    plan_sales: dict[str, dict] = {}
    async for sub in subscriptions.find({}):
        pname = sub.get("plan_name", "Неизвестный")
        if pname not in plan_sales:
            plan_sales[pname] = {"count": 0}
        plan_sales[pname]["count"] += 1

    # Активные подписки
    active_subs = await subscriptions.count_documents(
        {"expires_at": {"$gt": now.isoformat()}}
    )

    # Промокоды
    promos_used = 0
    async for p in payments.find({}):
        pass  # промокоды фиксируются через use_promo в billing

    promo_stats = []
    async for promo in promo_codes.find({}):
        promo_stats.append({
            "code": promo.get("code", ""),
            "discount": promo.get("discount_percent", 0),
            "uses": promo.get("uses_count", 0),
            "active": promo.get("active", False),
        })

    return {
        "total_revenue": total_revenue,
        "month_revenue": month_revenue,
        "today_revenue": today_revenue,
        "payment_count": payment_count,
        "active_subs": active_subs,
        "plan_sales": plan_sales,
        "promo_stats": promo_stats,
    }


# =========================
# 📊 Активность по разделам
# =========================
async def stats_activity() -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    actions = [
        "tutor", "practice", "calc",
        "pomodoro", "music", "todo",
        "lecture", "schedule", "attendance",
    ]
    labels = {
        "tutor": "🎓 ИИ-репетитор",
        "practice": "✍️ Практика",
        "calc": "🧮 Калькулятор",
        "pomodoro": "🍅 Помодоро",
        "music": "🎵 Музыка",
        "todo": "✅ To-Do",
        "lecture": "📖 Лекции",
        "schedule": "📆 Расписание",
        "attendance": "📍 Посещаемость",
    }

    result = {}
    for action in actions:
        total_count = await activity_log.count_documents({"action": action})
        day_count = await activity_log.count_documents({"action": action, "date": today})
        month_count = await activity_log.count_documents({"action": action, "month": month})
        result[action] = {
            "label": labels[action],
            "total": total_count,
            "today": day_count,
            "month": month_count,
        }

    return result


# =========================
# 🏆 Топ-10 пользователей по XP за месяц
# =========================
async def stats_top_xp(limit: int = 10) -> list:
    xp_log = db["xp_log"]
    month = datetime.now().strftime("%Y-%m")

    # Группируем XP по user_id за текущий месяц
    pipeline = [
        {"$match": {"ts": {"$gte": month}}},
        {"$group": {
            "_id": "$user_id",
            "xp_month": {"$sum": "$amount"},
            "actions": {"$push": "$action"},
        }},
        {"$sort": {"xp_month": -1}},
        {"$limit": limit},
    ]
    top = []
    async for doc in xp_log.aggregate(pipeline):
        user_id = doc["_id"]
        profile = await users.find_one({"user_id": user_id}, {"username": 1, "first_name": 1, "xp": 1})
        name = (profile or {}).get("first_name") or (profile or {}).get("username") or str(user_id)
        total_xp = (profile or {}).get("xp", 0)

        # Считаем разбивку по типам действий
        from collections import Counter
        action_counts = Counter(doc["actions"])
        breakdown = ", ".join(
            f"{a}×{c}" for a, c in action_counts.most_common(5)
        )

        top.append({
            "user_id": user_id,
            "name": name,
            "xp_month": doc["xp_month"],
            "xp_total": total_xp,
            "breakdown": breakdown,
        })

    return top


# =========================
# 📈 Динамика регистраций (последние 30 дней)
# =========================
async def stats_registrations_chart() -> list:
    result = []
    now = datetime.now()
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        count = await users.count_documents(
            {"first_seen": {"$gte": day, "$lt": (now - timedelta(days=i - 1)).strftime("%Y-%m-%d")}})
        result.append({"date": day, "count": count})
    return result


# =========================
# 📦 Полная сборка для экспорта
# =========================
async def get_full_stats() -> dict:
    u = await stats_users()
    f = await stats_finance()
    a = await stats_activity()
    t = await stats_top_xp()
    rc = await stats_registrations_chart()
    return {
        "users": u,
        "finance": f,
        "activity": a,
        "top_xp": t,
        "reg_chart": rc,
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }


# ==================================================

from database.mongo import db

trial_usage = db["trial_usage"]


async def get_trial_users():
    cursor = trial_usage.find({})
    return [doc async for doc in cursor]
