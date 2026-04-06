# =========================
# 📦 Импорты
# =========================
import os
import re
import base64
import asyncio
import aiohttp

from dotenv import load_dotenv
from yandex_ai_studio_sdk import AIStudio


# =========================
# 🔐 Конфиг (ENV)
# =========================
load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


# =========================
# 🧠 SYSTEM PROMPT (ядро логики)
# =========================
SYSTEM_PROMPT = """Ты — умный математический калькулятор-помощник.
Твоя задача — решать математические примеры, уравнения и задачи.

ВАЖНО: Ты реагируешь ТОЛЬКО на математические примеры и задачи.
ЕСЛИ пользователь пишет математическое выражение или задачу (даже если она написана словами, 
например "интеграл от x + 5", "производная x^2", "корень из 9", "реши уравнение 2x+1=5") — 
это ВСЕГДА задача, реши её.

Только если пользователь явно спрашивает теорию (например "что такое интеграл?", 
"объясни теорему Пифагора", "как вычислять производную?") — 
отвечай ТОЛЬКО: "Для этого зайдите в раздел ИИ-репетитор. Я умный калькулятор и помогаю только с решением примеров и задач :)"

Если это математическая задача или пример — решай по этим правилам:
1. Решай пошагово, каждый шаг на новой строке
2. Форматируй ответ строго в HTML:
   - Шаги решения оборачивай так: <b>Шаг 1:</b> текст
   - Математические выражения и числа оборачивай в <code>...</code>
   - Итоговый ответ оборачивай так: <b>Ответ:</b> <code>результат</code>
3. Если задача написана словами — сначала переведи в математическую форму
4. Если есть неизвестные — найди их значения
5. Если несколько примеров — реши каждый отдельно с заголовком <b>Задача 1:</b> и т.д.
6. Отвечай на том же языке что и задача
7. НИКОГДА не оборачивай весь ответ в блоки ``` или `код`. Используй только HTML теги указанные выше.

СТРОГО ЗАПРЕЩЕНО использовать LaTeX разметку: $, $$, \int, \frac, \, и любые другие LaTeX команды.
Вместо этого пиши формулы обычным текстом:
- дробь x²/2 пиши как x^2/2
- интеграл пиши как ∫
- умножение пиши как *
- корень пиши как √
Все математические выражения оборачивай в <code>...</code>

Для форматирования используй HTML теги:
- Степень пиши через <sup>: например 2<sup>18</sup>
- Нижний индекс пиши через <sub>: например x<sub>1</sub>
- Дробь пиши как числитель/знаменатель в <code>: например <code>x²/2</code>"""


# =========================
# 🏗 Инициализация SDK
# =========================
def get_sdk():
    return AIStudio(
        folder_id=YANDEX_FOLDER_ID,
        auth=YANDEX_API_KEY,
    )


# =========================
# 🧮 Решение задач (текст)
# =========================
async def solve_math(text: str) -> str:
    try:
        sdk = get_sdk()
        model = sdk.models.completions("yandexgpt").configure(temperature=0.1)

        loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(
            None,
            lambda: model.run([
                {"role": "system", "text": SYSTEM_PROMPT},
                {"role": "user", "text": text}
            ])
        )

        for alternative in result:
            text_result = alternative.text

            # Очистка от markdown-кода
            text_result = re.sub(r'```[\w]*\n?', '', text_result).strip()

            return text_result

        return "❌ Не удалось получить ответ от модели."

    except Exception as e:
        return f"❌ Ошибка ИИ: {str(e)}"


# =========================
# 🖼 OCR (распознавание текста)
# =========================
async def recognize_text_from_image(image_bytes: bytes) -> str:
    try:
        image_base64 = base64.b64encode(image_bytes).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "x-folder-id": YANDEX_FOLDER_ID,
                    "x-data-logging-enabled": "false",
                },
                json={
                    "content": image_base64,
                    "mimeType": "image/png",
                    "languageCodes": ["ru", "en"],
                    "model": "page",
                }
            ) as response:
                data = await response.json()

        blocks = data.get("result", {}).get("textAnnotation", {}).get("blocks", [])

        lines = []
        for block in blocks:
            for line in block.get("lines", []):
                line_text = " ".join(word.get("text", "") for word in line.get("words", []))
                lines.append(line_text)

        return "\n".join(lines).strip()

    except Exception:
        return ""


# =========================
# 📷 Решение по фото (LLM vision)
# =========================
async def solve_from_image(image_bytes: bytes) -> str:
    try:
        image_base64 = base64.b64encode(image_bytes).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "Реши задачу с фото пошагово."
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1
                }
            ) as resp:
                data = await resp.json()

        result = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not result:
            return "❌ Не удалось получить ответ от модели."

        result = re.sub(r'```[\w]*\n?', '', result).strip()

        return f"📷 <b>Решение по фото:</b>\n\n{result}"

    except Exception as e:
        return f"❌ Ошибка при обработке фото: {str(e)}"


# =========================
# 🎤 Голос → текст → решение
# =========================
async def solve_from_voice_text(voice_text: str) -> str:
    return await solve_math(f"Задача продиктована голосом: {voice_text}")