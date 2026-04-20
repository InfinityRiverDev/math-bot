import os
import aiohttp

STARS_TO_RUB = float(os.getenv("STARS_TO_RUB", 1.75))  # вручную

async def get_usdt_to_rub():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data["tether"]["rub"]


async def stars_to_rub(stars: float):
    return stars * STARS_TO_RUB


async def usdt_to_rub(usdt: float):
    rate = await get_usdt_to_rub()
    return usdt * rate