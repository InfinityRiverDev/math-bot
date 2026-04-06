# =========================
# 📦 Импорты
# =========================
import os
import re
import json
import base64
import asyncio
import aiohttp

from dotenv import load_dotenv


# =========================
# 🔐 Конфиг
# =========================
load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


# =========================
# 🧠 SYSTEM PROMPT
# =========================
TUTOR_PROMPT = """Ты — экспертный ИИ-репетитор по математике.
... (оставляем как есть)
"""


# =========================
# 🔤 Замена <sup>/<sub> → Unicode
# =========================
def replace_with_unicode(text: str) -> str:
    sup_map = {
        '0': '⁰','1': '¹','2': '²','3': '³','4': '⁴',
        '5': '⁵','6': '⁶','7': '⁷','8': '⁸','9': '⁹',
        'x': 'ˣ','n': 'ⁿ','+': '⁺','-': '⁻'
    }

    sub_map = {
        '0': '₀','1': '₁','2': '₂','3': '₃','4': '₄',
        '5': '₅','6': '₆','7': '₇','8': '₈','9': '₉',
        'x': 'ₓ','n': 'ₙ'
    }

    def sup(m): return "".join(sup_map.get(c, c) for c in m.group(1))
    def sub(m): return "".join(sub_map.get(c, c) for c in m.group(1))

    text = re.sub(r'<sup>(.*?)</sup>', sup, text)
    text = re.sub(r'<sub>(.*?)</sub>', sub, text)

    return text


# =========================
# 🧹 Очистка ответа модели
# =========================
def clean_response(text: str) -> str:
    if not text:
        return ""

    # списки
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE)

    # умножение
    text = re.sub(r'(\d)\s*\*\s*(\d)', r'\1 · \2', text)

    # sup/sub → unicode
    text = replace_with_unicode(text)

    # переносы
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # markdown → HTML
    text = re.sub(r'#{1,6}\s*(.+)', r'<b>\1</b>', text)

    # убираем LaTeX мусор
    text = (
        text.replace('$', '')
            .replace('\\(', '')
            .replace('\\)', '')
            .replace('\\[', '')
            .replace('\\]', '')
    )

    # фильтрация тегов
    text = re.sub(r'<(?!/?(b|i|code|pre|a)\b)[^>]+>', '', text)

    return text.strip()


# =========================
# 🎓 Репетитор (текст/документ)
# =========================
async def ask_tutor(text: str, history: list = None):
    try:
        messages = [{"role": "system", "content": TUTOR_PROMPT}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": text})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": True
                }
            ) as resp:

                async for line in resp.content:

                    # 🔴 проверка отмены
                    if asyncio.current_task().cancelled():
                        return

                    line = line.decode().strip()

                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')

                            if content:
                                for char in content:
                                    if asyncio.current_task().cancelled():
                                        return

                                    yield char
                                    await asyncio.sleep(0.005)

                        except:
                            continue

    except asyncio.CancelledError:
        return

    except Exception as e:
        yield f"❌ Ошибка: {str(e)}"


# =========================
# 📷 Репетитор (фото)
# =========================
async def ask_tutor_image(image_bytes: bytes, history: list = None):
    try:
        image_base64 = base64.b64encode(image_bytes).decode()

        messages = [{"role": "system", "content": TUTOR_PROMPT}]

        if history:
            messages.extend(history)

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                },
                {
                    "type": "text",
                    "text": "Объясни задачу или тему с этого фото."
                }
            ]
        })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": True
                }
            ) as resp:

                async for line in resp.content:

                    if asyncio.current_task().cancelled():
                        return

                    line = line.decode().strip()

                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')

                            if content:
                                for char in content:
                                    if asyncio.current_task().cancelled():
                                        return

                                    yield char
                                    await asyncio.sleep(0.005)

                        except:
                            continue

    except asyncio.CancelledError:
        return

    except Exception as e:
        yield f"❌ Ошибка фото: {str(e)}"


# =========================
# 🎤 Голос → текст
# =========================
async def speech_to_text(file_bytes: bytes) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                headers={"Authorization": f"Api-Key {YANDEX_API_KEY}"},
                params={
                    "topic": "general",
                    "folderId": YANDEX_FOLDER_ID,
                    "lang": "ru-RU"
                },
                data=file_bytes
            ) as resp:
                data = await resp.json()
                return data.get("result", "")

    except Exception:
        return ""