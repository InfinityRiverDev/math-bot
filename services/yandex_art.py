"""
services/yandex_art.py
Генерация изображений через Yandex ART API.
"""
import os
import asyncio
import aiohttp
import logging

logger = logging.getLogger(__name__)

YANDEX_API_KEY   = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

ART_URL      = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
OPERATION_URL = "https://llm.api.cloud.yandex.net/operations/"

HEADERS = lambda: {
    "Authorization": f"Api-Key {YANDEX_API_KEY}",
    "Content-Type": "application/json",
    "x-folder-id": YANDEX_FOLDER_ID,
}


async def generate_image(prompt: str, style: str = "DEFAULT") -> bytes | None:
    """
    Генерирует изображение по промпту.
    Возвращает байты PNG или None при ошибке.
    
    style: DEFAULT | ANIME | KANDINSKY
    """
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        logger.error("[ART] API ключи не заданы")
        return None

    payload = {
        "modelUri": f"art://{YANDEX_FOLDER_ID}/yandex-art/latest",
        "generationOptions": {
            "seed": 42,
            "aspectRatio": {
                "widthRatio": "1",
                "heightRatio": "1"
            }
        },
        "messages": [
            {
                "weight": "1",
                "text": prompt
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Шаг 1 — запускаем асинхронную генерацию
            async with session.post(ART_URL, json=payload, headers=HEADERS()) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"[ART] Ошибка запуска: {resp.status} {text[:200]}")
                    return None
                data = await resp.json()
                operation_id = data.get("id")
                if not operation_id:
                    logger.error(f"[ART] Нет operation_id: {data}")
                    return None

            logger.info(f"[ART] Operation started: {operation_id}")

            # Шаг 2 — polling результата (обычно 10-30 сек)
            for attempt in range(30):
                await asyncio.sleep(3)
                async with session.get(
                    f"{OPERATION_URL}{operation_id}",
                    headers=HEADERS()
                ) as poll:
                    result = await poll.json()
                    if result.get("done"):
                        image_data = result.get("response", {}).get("image")
                        if not image_data:
                            logger.error(f"[ART] Нет image в ответе: {result}")
                            return None
                        # image_data — base64 строка
                        import base64
                        return base64.b64decode(image_data)
                    
                    error = result.get("error")
                    if error:
                        logger.error(f"[ART] Ошибка генерации: {error}")
                        return None
                    
                    logger.info(f"[ART] Attempt {attempt+1}/30, still processing...")

            logger.error("[ART] Timeout — генерация заняла слишком долго")
            return None

    except Exception as e:
        logger.error(f"[ART] Exception: {e}")
        return None