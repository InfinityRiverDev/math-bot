"""
handlers/stats.py

Полная статистика для администратора.
Многостраничная навигация + экспорт в Excel.

Подключить в main.py:
    from handlers import stats as stats_handler
    dp.include_router(stats_handler.router)

Также нужно вызывать log_activity() из хэндлеров —
см. раздел «Что добавить в другие файлы» в конце.
"""

import io
import os
import tempfile
import html
from datetime import datetime
from tkinter import Image

from aiogram import F, Router, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.exceptions import TelegramBadRequest

from handlers.admin import ADMIN_IDS
from database.stats_models import (
    stats_users, stats_finance, stats_activity,
    stats_top_xp, stats_registrations_chart, get_full_stats,
    )


router = Router()


# =========================
# 🔧 Утилиты
# =========================
async def safe_edit(msg, text: str, markup=None):
    try:
        await msg.edit_text(text, reply_markup=markup, parse_mode='HTML')
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _money(v) -> str:
    return f"{v:,.0f}₽".replace(",", " ")


def _num(v) -> str:
    return f"{v:,}".replace(",", " ")


# =========================
# 🎛 Клавиатуры
# =========================
def kb_stats_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="stats_users"),
            InlineKeyboardButton(text="💰 Финансы", callback_data="stats_finance"),
        ],
        [
            InlineKeyboardButton(text="📊 Активность", callback_data="stats_activity"),
            InlineKeyboardButton(text="🏆 Топ XP", callback_data="stats_top_xp"),
        ],
        [
            InlineKeyboardButton(text="📈 Динамика", callback_data="stats_chart"),
        ],
        [
            InlineKeyboardButton(text="📥 Экспорт", callback_data="stats_export_choose"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main"),
        ],
    ])


def kb_export_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Excel", callback_data="stats_export_excel"),
            InlineKeyboardButton(text="📄 PDF", callback_data="stats_export_pdf"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_statistics"),
        ],
    ])

def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_refresh"),
            InlineKeyboardButton(text="⬅️ К разделам", callback_data="admin_statistics"),
        ],
    ])


def kb_back_with_export() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_refresh"),
            InlineKeyboardButton(text="📥 Excel", callback_data="stats_export"),
        ],
        [InlineKeyboardButton(text="⬅️ К разделам", callback_data="admin_statistics")],
    ])


# =========================
# 🏠 Главное меню статистики
# =========================
@router.callback_query(F.data == "admin_statistics", F.from_user.id.in_(ADMIN_IDS))
async def stats_main(callback: CallbackQuery):
    await callback.answer()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    await safe_edit(
        callback.message,
        f"📊 <b>Статистика бота</b>\n\n"
        f"Выбери раздел для просмотра.\n"
        f"<i>Обновлено: {now}</i>",
        kb_stats_main()
    )


@router.callback_query(F.data == "stats_refresh", F.from_user.id.in_(ADMIN_IDS))
async def stats_refresh(callback: CallbackQuery):
    await callback.answer("🔄 Обновлено")
    await stats_main(callback)


# =========================
# 👥 Пользователи
# =========================
@router.callback_query(F.data == "stats_users", F.from_user.id.in_(ADMIN_IDS))
async def stats_show_users(callback: CallbackQuery):
    await callback.answer()
    u = await stats_users()

    sub_pct = round(u["with_sub"] / u["total"] * 100, 1) if u["total"] else 0
    conv_bar = _bar(sub_pct, 100)

    text = (
        "👥 <b>Пользователи</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"

        "📌 <b>Общее</b>\n"
        f"  Всего зарегистрировано: <b>{_num(u['total'])}</b>\n"
        f"  С активной подпиской:   <b>{_num(u['with_sub'])}</b>\n"
        f"  Без подписки:           <b>{_num(u['no_sub'])}</b>\n\n"

        f"  Конверсия в подписку:\n"
        f"  {conv_bar} <b>{sub_pct}%</b>\n\n"

        "🆕 <b>Прирост</b>\n"
        f"  Сегодня:   <b>+{u['new_today']}</b>\n"
        f"  За неделю: <b>+{u['new_week']}</b>\n"
        f"  За месяц:  <b>+{u['new_month']}</b>\n"
    )
    await safe_edit(callback.message, text, kb_back())


# =========================
# 💰 Финансы
# =========================
@router.callback_query(F.data == "stats_finance", F.from_user.id.in_(ADMIN_IDS))
async def stats_show_finance(callback: CallbackQuery):
    await callback.answer()
    f = await stats_finance()

    plan_lines = ""
    if f["plan_sales"]:
        for pname, data in sorted(f["plan_sales"].items(), key=lambda x: -x[1]["count"]):
            plan_lines += f"  • {pname}: <b>{data['count']}</b> покупок\n"
    else:
        plan_lines = "  Данных пока нет\n"

    promo_lines = ""
    if f["promo_stats"]:
        for p in sorted(f["promo_stats"], key=lambda x: -x["uses"]):
            status = "✅" if p["active"] else "❌"
            promo_lines += (
                f"  {status} <code>{p['code']}</code> "
                f"−{p['discount']}%  |  использований: <b>{p['uses']}</b>\n"
            )
    else:
        promo_lines = "  Промокодов нет\n"

    text = (
        "💰 <b>Финансы</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"

        "💵 <b>Выручка</b>\n"
        f"  Сегодня:   <b>{_money(f['today_revenue'])}</b>\n"
        f"  За месяц:  <b>{_money(f['month_revenue'])}</b>\n"
        f"  Всего:     <b>{_money(f['total_revenue'])}</b>\n"
        f"  Платежей:  <b>{_num(f['payment_count'])}</b>\n\n"

        "📦 <b>Подписки</b>\n"
        f"  Активных сейчас: <b>{f['active_subs']}</b>\n\n"

        "📋 <b>Продажи по тарифам</b>\n"
        f"{plan_lines}\n"

        "🎟 <b>Промокоды</b>\n"
        f"{promo_lines}"
    )
    await safe_edit(callback.message, text, kb_back_with_export())


# =========================
# 📊 Активность по разделам
# =========================
@router.callback_query(F.data == "stats_activity", F.from_user.id.in_(ADMIN_IDS))
async def stats_show_activity(callback: CallbackQuery):
    await callback.answer()
    a = await stats_activity()

    # Сортируем по количеству за месяц
    sorted_actions = sorted(a.values(), key=lambda x: -x["month"])

    lines = ""
    for item in sorted_actions:
        lines += (
            f"{item['label']}\n"
            f"  сегодня <b>{_num(item['today'])}</b>  "
            f"│ месяц <b>{_num(item['month'])}</b>  "
            f"│ всего <b>{_num(item['total'])}</b>\n\n"
        )

    # Самый популярный раздел
    if sorted_actions:
        top = sorted_actions[0]
        popular = f"🔥 Самый активный раздел: {top['label']} ({_num(top['month'])} за месяц)\n\n"
    else:
        popular = ""

    text = (
        "📊 <b>Активность по разделам</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"{popular}"
        f"{lines}"
    )
    await safe_edit(callback.message, text, kb_back_with_export())


# =========================
# 🏆 Топ XP
# =========================
@router.callback_query(F.data == "stats_top_xp", F.from_user.id.in_(ADMIN_IDS))
async def stats_show_top_xp(callback: CallbackQuery):
    await callback.answer()
    top = await stats_top_xp(10)

    if not top:
        await safe_edit(
            callback.message,
            "🏆 <b>Топ пользователей по XP</b>\n\n"
            "Данных пока нет — XP ещё не начислялись.",
            kb_back()
        )
        return

    medals = ["🥇", "🥈", "🥉"] + ["▪️"] * 10
    lines = ""
    for i, user in enumerate(top):
        lines += (
            f"{medals[i]} <b>{user['name']}</b>  "
            f"<code>{user['user_id']}</code>\n"
            f"   +{_num(user['xp_month'])} XP за месяц  │  "
            f"{_num(user['xp_total'])} всего\n"
            f"   <i>{user['breakdown']}</i>\n\n"
        )

    text = (
        "🏆 <b>Топ-10 пользователей за месяц</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"{lines}"
        "─────────────────────\n"
        "<i>В скобках — разбивка заработанных XP по действиям.\n"
        "Подозрительно много одного типа = возможный абуз.</i>"
    )
    await safe_edit(callback.message, text, kb_back_with_export())


# =========================
# 📈 Динамика регистраций
# =========================
@router.callback_query(F.data == "stats_chart", F.from_user.id.in_(ADMIN_IDS))
async def stats_show_chart(callback: CallbackQuery):
    await callback.answer()
    chart = await stats_registrations_chart()

    if not any(d["count"] for d in chart):
        await safe_edit(
            callback.message,
            "<b>Динамика регистраций (30 дней)</b>\n\nДанных пока нет.",
            kb_back()
        )
        return

    # ASCII-спарклайн
    max_val = max(d["count"] for d in chart) or 1
    blocks = " ▁▂▃▄▅▆▇█"

    spark = ""
    for d in chart:
        idx = min(int(d["count"] / max_val * 8), 8)
        spark += blocks[idx]

    # Итоги
    total_month = sum(d["count"] for d in chart)
    peak = max(chart, key=lambda x: x["count"])
    last7 = sum(d["count"] for d in chart[-7:])
    prev7 = sum(d["count"] for d in chart[-14:-7])
    trend = "📈" if last7 >= prev7 else "📉"
    delta = last7 - prev7

    text = (
        "📈 <b>Динамика регистраций (30 дней)</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"<code>{spark}</code>\n\n"
        f"  За 30 дней:   <b>{_num(total_month)}</b> новых\n"
        f"  Пик:          <b>{peak['count']}</b> ({peak['date']})\n\n"
        f"  Последние 7 дней: <b>{last7}</b>\n"
        f"  Предыдущие 7 дней: <b>{prev7}</b>\n"
        f"  Тренд: {trend} <b>{'+' if delta >= 0 else ''}{delta}</b>\n\n"
        "<i>Каждый символ = 1 день слева направо</i>"
    )
    await safe_edit(callback.message, text, kb_back_with_export())


# =========================
# 📥 Экспорт в Excel
# =========================
@router.callback_query(F.data == "stats_export_choose", F.from_user.id.in_(ADMIN_IDS))
async def stats_export_choose(callback: CallbackQuery):
    await callback.answer()
    await safe_edit(
        callback.message,
        "📥 <b>Выбери формат экспорта:</b>",
        kb_export_choice()
    )


@router.callback_query(F.data == "stats_export_excel", F.from_user.id.in_(ADMIN_IDS))
async def stats_export(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await safe_edit(callback.message, "📊 Собираю данные и формирую Excel...")

    try:
        data = await get_full_stats()
        xlsx_buf = await _build_xlsx(data)
        fname = f"stats_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        await bot.send_document(
            chat_id=callback.from_user.id,
            document=BufferedInputFile(xlsx_buf.getvalue(), filename=fname),
            caption=(
                f"📊 <b>Статистика бота</b>\n"
                f"Сформирована: {data['generated_at']}\n\n"
                "Листы: Пользователи, Финансы, Активность, Топ XP, Динамика"
            ),
            parse_mode='HTML'
        )
        await safe_edit(
            callback.message,
            "✅ <b>Файл отправлен!</b>\n\nПроверь сообщения выше 👆",
            kb_stats_main()
        )
    except Exception as e:
        err = html.escape(str(e))[:200]
        await safe_edit(
            callback.message,
            f"❌ <b>Ошибка при формировании файла</b>\n\n<code>{err}</code>",
            kb_stats_main()
        )


# =========================
# 🔨 Построение Excel
# =========================
async def _build_xlsx(data: dict) -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference, LineChart

    wb = Workbook()
    now = data["generated_at"]

    # Цвета
    C_HEADER = "1F3864"  # тёмно-синий
    C_SUBHEAD = "2E75B6"  # синий
    C_ACCENT = "D6E4F7"  # светло-голубой
    C_GREEN = "E2EFDA"  # светло-зелёный
    C_YELLOW = "FFF2CC"  # жёлтый
    C_RED = "FCE4D6"  # красный

    thin = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    def header_cell(ws, row, col, text, bg=C_HEADER, fg="FFFFFF", bold=True, size=11):
        c = ws.cell(row=row, column=col, value=text)
        c.font = Font(bold=bold, color=fg, name="Arial", size=size)
        c.fill = PatternFill("solid", start_color=bg)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin
        return c

    def data_cell(ws, row, col, value, bg=None, bold=False, fmt=None, align="left"):
        c = ws.cell(row=row, column=col, value=value)
        c.font = Font(name="Arial", size=10, bold=bold)
        c.alignment = Alignment(horizontal=align, vertical="center")
        c.border = thin
        if bg:
            c.fill = PatternFill("solid", start_color=bg)
        if fmt:
            c.number_format = fmt
        return c

    def set_col_widths(ws, widths: list):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    def title_row(ws, text, cols=6):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=cols)
        c = ws.cell(row=1, column=1, value=text)
        c.font = Font(bold=True, size=14, color="FFFFFF", name="Arial")
        c.fill = PatternFill("solid", start_color=C_HEADER)
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=cols)
        c2 = ws.cell(row=2, column=1, value=f"Сформировано: {now}")
        c2.font = Font(italic=True, size=9, color="666666", name="Arial")
        c2.alignment = Alignment(horizontal="center")

    # ──────────────────────────────
    # Лист 1: Пользователи
    # ──────────────────────────────
    ws1 = wb.active
    ws1.title = "Пользователи"
    title_row(ws1, "👥 Статистика пользователей", 3)

    u = data["users"]
    ws1.row_dimensions[4].height = 18
    header_cell(ws1, 4, 1, "Метрика", bg=C_SUBHEAD)
    header_cell(ws1, 4, 2, "Значение", bg=C_SUBHEAD)
    header_cell(ws1, 4, 3, "Комментарий", bg=C_SUBHEAD)

    rows_u = [
        ("Всего пользователей", u["total"], ""),
        ("С активной подпиской", u["with_sub"],
         f"{round(u['with_sub'] / u['total'] * 100, 1) if u['total'] else 0}% конверсия"),
        ("Без подписки", u["no_sub"], ""),
        ("Новых сегодня", u["new_today"], ""),
        ("Новых за неделю", u["new_week"], ""),
        ("Новых за месяц", u["new_month"], ""),
    ]
    for i, (label, val, comment) in enumerate(rows_u, 5):
        bg = C_ACCENT if i % 2 == 0 else None
        data_cell(ws1, i, 1, label, bg=bg)
        data_cell(ws1, i, 2, val, bg=bg, bold=True, align="center")
        data_cell(ws1, i, 3, comment, bg=bg)

    set_col_widths(ws1, [32, 16, 30])

    # ──────────────────────────────
    # Лист 2: Финансы
    # ──────────────────────────────
    ws2 = wb.create_sheet("Финансы")
    title_row(ws2, "💰 Финансовая статистика", 4)

    f = data["finance"]

    header_cell(ws2, 4, 1, "Метрика", bg=C_SUBHEAD)
    header_cell(ws2, 4, 2, "Значение", bg=C_SUBHEAD)
    header_cell(ws2, 4, 3, "Период", bg=C_SUBHEAD)
    header_cell(ws2, 4, 4, "Примечание", bg=C_SUBHEAD)

    rows_f = [
        ("Выручка", f["today_revenue"], "Сегодня", "₽"),
        ("Выручка", f["month_revenue"], "Месяц", "₽"),
        ("Выручка", f["total_revenue"], "Всего", "₽"),
        ("Кол-во платежей", f["payment_count"], "Всего", "шт."),
        ("Активных подписок", f["active_subs"], "Сейчас", ""),
    ]
    for i, (label, val, period, unit) in enumerate(rows_f, 5):
        bg = C_GREEN if i % 2 == 0 else None
        data_cell(ws2, i, 1, label, bg=bg)
        data_cell(ws2, i, 2, val, bg=bg, bold=True, align="center",
                  fmt='#,##0.00' if unit == "₽" else '#,##0')
        data_cell(ws2, i, 3, period, bg=bg, align="center")
        data_cell(ws2, i, 4, unit, bg=bg, align="center")

    # Продажи по тарифам
    row = len(rows_f) + 6
    ws2.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    header_cell(ws2, row, 1, "Продажи по тарифам", bg=C_SUBHEAD)
    row += 1
    header_cell(ws2, row, 1, "Тариф", bg=C_SUBHEAD)
    header_cell(ws2, row, 2, "Покупок", bg=C_SUBHEAD)
    row += 1
    for pname, pdata in sorted(f["plan_sales"].items(), key=lambda x: -x[1]["count"]):
        bg = C_YELLOW if row % 2 == 0 else None
        data_cell(ws2, row, 1, pname, bg=bg)
        data_cell(ws2, row, 2, pdata["count"], bg=bg, bold=True, align="center")
        row += 1

    if not f["plan_sales"]:
        data_cell(ws2, row, 1, "Нет данных")
        row += 1

    # Промокоды
    row += 1
    ws2.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
    header_cell(ws2, row, 1, "Промокоды", bg=C_SUBHEAD)
    row += 1
    header_cell(ws2, row, 1, "Код", bg=C_SUBHEAD)
    header_cell(ws2, row, 2, "Скидка", bg=C_SUBHEAD)
    header_cell(ws2, row, 3, "Исп-й", bg=C_SUBHEAD)
    header_cell(ws2, row, 4, "Активен", bg=C_SUBHEAD)
    row += 1
    for p in sorted(f["promo_stats"], key=lambda x: -x["uses"]):
        bg = C_GREEN if p["active"] else C_RED
        data_cell(ws2, row, 1, p["code"], bg=bg, bold=True)
        data_cell(ws2, row, 2, f"{p['discount']}%", bg=bg, align="center")
        data_cell(ws2, row, 3, p["uses"], bg=bg, align="center", bold=True)
        data_cell(ws2, row, 4, "Да" if p["active"] else "Нет", bg=bg, align="center")
        row += 1

    # 📊 KPI рост выручки (сегодня vs среднее)
    avg = f["month_revenue"] / 30 if f["month_revenue"] else 0
    delta = f["today_revenue"] - avg

    # безопасно определяем строку
    last_row = ws2.max_row + 2

    data_cell(ws2, last_row, 1, "Отклонение от среднего", bold=True)

    cell = ws2.cell(row=last_row, column=2, value=delta)
    cell.font = Font(bold=True)

    if delta > 0:
        cell.fill = PatternFill("solid", start_color=C_GREEN)
    elif delta < 0:
        cell.fill = PatternFill("solid", start_color=C_RED)
    else:
        cell.fill = PatternFill("solid", start_color=C_YELLOW)

    cell.alignment = Alignment(horizontal="center")
    cell.border = thin

    set_col_widths(ws2, [28, 16, 14, 20])

    # ──────────────────────────────
    # Лист 3: Активность
    # ──────────────────────────────
    ws3 = wb.create_sheet("Активность")
    title_row(ws3, "📊 Активность по разделам", 5)

    header_cell(ws3, 4, 1, "Раздел", bg=C_SUBHEAD)
    header_cell(ws3, 4, 2, "Сегодня", bg=C_SUBHEAD)
    header_cell(ws3, 4, 3, "За месяц", bg=C_SUBHEAD)
    header_cell(ws3, 4, 4, "Всего", bg=C_SUBHEAD)
    header_cell(ws3, 4, 5, "Доля месяца", bg=C_SUBHEAD)

    a = data["activity"]
    items = sorted(a.values(), key=lambda x: -x["month"])
    total_month = sum(x["month"] for x in items) or 1

    for i, item in enumerate(items, 5):
        bg = C_ACCENT if i % 2 == 0 else None
        share = round(item["month"] / total_month * 100, 1)
        data_cell(ws3, i, 1, item["label"], bg=bg)
        data_cell(ws3, i, 2, item["today"], bg=bg, align="center", bold=True)
        data_cell(ws3, i, 3, item["month"], bg=bg, align="center", bold=True)
        data_cell(ws3, i, 4, item["total"], bg=bg, align="center")
        data_cell(ws3, i, 5, f"{share}%", bg=bg, align="center")

    set_col_widths(ws3, [26, 12, 14, 14, 16])

    # ──────────────────────────────
    # Лист 4: Топ XP
    # ──────────────────────────────
    ws4 = wb.create_sheet("Топ XP")
    title_row(ws4, "🏆 Топ пользователей по XP за месяц", 6)

    header_cell(ws4, 4, 1, "#", bg=C_SUBHEAD)
    header_cell(ws4, 4, 2, "Имя", bg=C_SUBHEAD)
    header_cell(ws4, 4, 3, "User ID", bg=C_SUBHEAD)
    header_cell(ws4, 4, 4, "XP месяц", bg=C_SUBHEAD)
    header_cell(ws4, 4, 5, "XP всего", bg=C_SUBHEAD)
    header_cell(ws4, 4, 6, "Разбивка действий", bg=C_SUBHEAD)

    medals_bg = [C_YELLOW, "D9D9D9", "F4CCCC"] + [None] * 20

    for i, user in enumerate(data["top_xp"], 5):
        rank = i - 4
        bg = medals_bg[rank - 1]
        data_cell(ws4, i, 1, rank, bg=bg, bold=(rank <= 3), align="center")
        data_cell(ws4, i, 2, user["name"], bg=bg, bold=(rank <= 3))
        data_cell(ws4, i, 3, str(user["user_id"]), bg=bg, align="center")
        data_cell(ws4, i, 4, user["xp_month"], bg=bg, bold=True, align="center", fmt='#,##0')
        data_cell(ws4, i, 5, user["xp_total"], bg=bg, align="center", fmt='#,##0')
        data_cell(ws4, i, 6, user["breakdown"], bg=bg)

    if not data["top_xp"]:
        data_cell(ws4, 5, 1, "Нет данных")

    set_col_widths(ws4, [6, 22, 14, 12, 12, 40])

    # 🏆 График XP
    if data["top_xp"]:
        chart = BarChart()
        chart.title = "Топ XP за месяц"
        chart.y_axis.title = "XP"
        chart.x_axis.title = "Пользователи"

        data_ref = Reference(ws4, min_col=4, min_row=4, max_row=4 + len(data["top_xp"]))
        cats_ref = Reference(ws4, min_col=2, min_row=5, max_row=4 + len(data["top_xp"]))

        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)

        chart.height = 12
        chart.width = 22

        ws4.add_chart(chart, "H4")

    # ──────────────────────────────
    # Лист 5: Динамика регистраций
    # ──────────────────────────────
    ws5 = wb.create_sheet("Динамика")
    title_row(ws5, "📈 Динамика регистраций (30 дней)", 2)

    header_cell(ws5, 4, 1, "Дата", bg=C_SUBHEAD)
    header_cell(ws5, 4, 2, "Новых", bg=C_SUBHEAD)

    for i, item in enumerate(data["reg_chart"], 5):
        bg = C_GREEN if item["count"] > 0 else None
        data_cell(ws5, i, 1, item["date"], bg=bg)
        data_cell(ws5, i, 2, item["count"], bg=bg, bold=item["count"] > 0, align="center")

    # Итог
    total_row = len(data["reg_chart"]) + 5

    # 📊 KPI тренд (последние 7 дней vs предыдущие)
    last7 = sum(x["count"] for x in data["reg_chart"][-7:])
    prev7 = sum(x["count"] for x in data["reg_chart"][-14:-7])

    trend_cell = ws5.cell(row=total_row + 1, column=1, value="Тренд (7 дней)")
    trend_value = last7 - prev7

    cell = ws5.cell(row=total_row + 1, column=2, value=trend_value)
    cell.font = Font(bold=True)

    if trend_value > 0:
        cell.fill = PatternFill("solid", start_color=C_GREEN)
    elif trend_value < 0:
        cell.fill = PatternFill("solid", start_color=C_RED)
    else:
        cell.fill = PatternFill("solid", start_color=C_YELLOW)

    cell.alignment = Alignment(horizontal="center")
    cell.border = thin

    data_cell(ws5, total_row, 1, "ИТОГО за 30 дней", bold=True, bg=C_YELLOW)
    ws5.cell(row=total_row, column=2).value = f'=SUM(B5:B{total_row - 1})'
    ws5.cell(row=total_row, column=2).font = Font(bold=True, name="Arial", size=10)
    ws5.cell(row=total_row, column=2).fill = PatternFill("solid", start_color=C_YELLOW)
    ws5.cell(row=total_row, column=2).alignment = Alignment(horizontal="center")
    ws5.cell(row=total_row, column=2).border = thin

    set_col_widths(ws5, [14, 10])

    # 📈 График регистраций
    chart = LineChart()
    chart.title = "Регистрации по дням"
    chart.y_axis.title = "Пользователи"
    chart.x_axis.title = "Дата"

    data_ref = Reference(ws5, min_col=2, min_row=4, max_row=total_row - 1)
    cats_ref = Reference(ws5, min_col=1, min_row=5, max_row=total_row - 1)

    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    chart.height = 10
    chart.width = 22

    ws5.add_chart(chart, f"D4")

    # ──────────────────────────────
    # Сохраняем
    # ──────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# =========================
# 🔧 Прогресс-бар
# =========================
def _bar(value: float, maximum: float, length: int = 8) -> str:
    if maximum == 0:
        return "⬜" * length
    filled = min(int(length * value / maximum), length)
    return "🟦" * filled + "⬜" * (length - filled)



# =========================
# 📥 Экспорт в PDF
# =========================
def _generate_insights(data: dict) -> list[str]:
    insights = []

    u = data["users"]
    f = data["finance"]

    # ===== 📊 Конверсия =====
    if u["total"]:
        conv = u["with_sub"] / u["total"] * 100
        insights.append(f"Конверсия: {conv:.1f}%")

    # ===== 💰 Выручка =====
    avg = f["month_revenue"] / 30 if f["month_revenue"] else 0
    today = f["today_revenue"]

    if avg > 0:
        delta_pct = (today - avg) / avg * 100

        if delta_pct > 0:
            insights.append(f"📈 Выручка выросла на {delta_pct:.1f}%")
        else:
            insights.append(f"📉 Выручка упала на {abs(delta_pct):.1f}%")

    # ===== 📈 Регистрации =====
    last7 = sum(x["count"] for x in data["reg_chart"][-7:])
    prev7 = sum(x["count"] for x in data["reg_chart"][-14:-7])

    if prev7 > 0:
        delta = (last7 - prev7) / prev7 * 100
        if delta > 0:
            insights.append(f"📈 Регистрации выросли на {delta:.1f}%")
        else:
            insights.append(f"📉 Регистрации упали на {abs(delta):.1f}%")

    # ===== 🏆 Аномалии =====
    if data["top_xp"]:
        top = data["top_xp"][0]
        if top["xp_month"] > 5000:
            insights.append(f"⚠️ Аномально высокий XP у {top['name']}")

    return insights


async def _build_pdf(data: dict) -> io.BytesIO:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("DejaVu", "media/fonts/DejaVuSans.ttf"))

    import io
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"
    styles["Heading1"].fontName = "DejaVu"
    styles["Heading2"].fontName = "DejaVu"
    elements = []

    # ===== Заголовок =====
    elements.append(Paragraph("Статистика бота", styles["Title"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Сформировано: {data['generated_at']}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # ===== 🧠 Авто-анализ =====
    insights = _generate_insights(data)

    elements.append(Paragraph("Авто-анализ", styles["Heading2"]))
    for ins in insights:
        elements.append(Paragraph(ins, styles["Normal"]))
    elements.append(Spacer(1, 20))

    # ===== 👥 Пользователи =====
    u = data["users"]

    elements.append(Paragraph("Пользователи", styles["Heading2"]))

    table = Table([
        ["Метрика", "Значение"],
        ["Всего", u["total"]],
        ["С подпиской", u["with_sub"]],
        ["Без подписки", u["no_sub"]],
        ["Сегодня", u["new_today"]],
        ["Неделя", u["new_week"]],
        ["Месяц", u["new_month"]],
    ])

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # ===== 💰 Финансы =====
    f = data["finance"]

    elements.append(Paragraph("Финансы", styles["Heading2"]))

    table = Table([
        ["Метрика", "Значение"],
        ["Сегодня", f["today_revenue"]],
        ["Месяц", f["month_revenue"]],
        ["Всего", f["total_revenue"]],
        ["Платежи", f["payment_count"]],
        ["Активные подписки", f["active_subs"]],
    ])

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # ===== 📊 Активность =====
    elements.append(Paragraph("Активность", styles["Heading2"]))

    activity_data = [["Раздел", "Сегодня", "Месяц", "Всего"]]

    for item in data["activity"].values():
        activity_data.append([
            item["label"],
            item["today"],
            item["month"],
            item["total"]
        ])

    table = Table(activity_data)

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # ===== 📈 Динамика =====
    elements.append(Paragraph("Динамика регистраций", styles["Heading2"]))

    chart_data = [["Дата", "Новые"]]

    for d in data["reg_chart"]:
        chart_data.append([d["date"], d["count"]])

    table = Table(chart_data)

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
    ]))

    elements.append(table)

    # ===== Сборка =====
    doc.build(elements)
    buf.seek(0)
    return buf

@router.callback_query(F.data == "stats_export_pdf", F.from_user.id.in_(ADMIN_IDS))
async def stats_export_pdf(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await safe_edit(callback.message, "📄 Формирую PDF...")

    try:
        data = await get_full_stats()
        pdf_buf = await _build_pdf(data)

        fname = f"stats_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        await bot.send_document(
            chat_id=callback.from_user.id,
            document=BufferedInputFile(pdf_buf.getvalue(), filename=fname),
            caption="📄 PDF готов",
        )

        await safe_edit(
            callback.message,
            "✅ PDF отправлен!",
            kb_stats_main()
        )

    except Exception as e:
        import html
        err = html.escape(str(e))[:200]
        await safe_edit(
            callback.message,
            f"❌ <b>Ошибка PDF</b>\n\n<code>{err}</code>",
            kb_stats_main()
        )