import aiohttp
import os

CRYPTO_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")

BOT_USERNAME = os.getenv("BOT_USERNAME")

BASE_URL = "https://pay.crypt.bot/api"



# ===========================
# 🧾 СОЗДАНИЕ ИНВОЙСА
# ===========================

async def create_crypto_invoice(amount: float, user_id: int):
    """
    Создаёт invoice в CryptoBot

    :param amount: сумма в USDT
    :param user_id: id пользователя (кладём в hidden_message)
    :return: dict ответа API
    """
    url = f"{BASE_URL}/createInvoice"

    headers = {
        "Crypto-Pay-API-Token": CRYPTO_TOKEN
    }

    data = {
        "asset": "USDT",
        "amount": amount,
        "description": f"Пополнение баланса (user {user_id})",

        # после оплаты кнопка "Вернуться в бота"
        "paid_btn_name": "openBot",
        "paid_btn_url": f"https://t.me/{BOT_USERNAME}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            result = await resp.json()

            if not result.get("ok"):
                raise Exception(f"CryptoBot error: {result}")

            return result["result"]


# ===========================
# 🔍 ПРОВЕРКА ИНВОЙСА
# ===========================

async def get_crypto_invoice(invoice_id: str):
    """
    Получает информацию об инвойсе
    """
    url = f"{BASE_URL}/getInvoices"

    headers = {
        "Crypto-Pay-API-Token": CRYPTO_TOKEN
    }

    params = {
        "invoice_ids": invoice_id
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            result = await resp.json()

            if not result.get("ok"):
                raise Exception(f"CryptoBot error: {result}")

            items = result["result"]["items"]
            return items[0] if items else None


# ===========================
# ✅ ПРОВЕРКА ОПЛАТЫ
# ===========================

async def is_crypto_paid(invoice_id: str) -> bool:
    """
    Проверяет, оплачен ли инвойс
    """
    invoice = await get_crypto_invoice(invoice_id)

    if not invoice:
        return False

    return invoice.get("status") == "paid"


# ===========================
# 🔁 ВСПОМОГАТЕЛЬНОЕ
# ===========================

async def get_invoice_status(invoice_id: str) -> str:
    """
    Возвращает статус:
    active / paid / expired
    """
    invoice = await get_crypto_invoice(invoice_id)

    if not invoice:
        return "not_found"

    return invoice.get("status")

