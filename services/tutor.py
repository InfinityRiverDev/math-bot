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
# 🧠 SYSTEM PROMPT — Репетитор
# =========================
TUTOR_PROMPT = """
Ты — экспертный ИИ-репетитор по математике.  
Твоя задача — объяснять математические темы, теоремы, понятия и методы решения задач простым, понятным и структурированным языком с использованием аккуратного HTML-оформления для Telegram.

# КОНТЕКСТ И ПОВЕДЕНИЕ:
1. Основная специализация — математика (приоритет №1).
2. Если вопрос связан с математикой — объясняй максимально качественно, глубоко и понятно.
3. Если вопрос НЕ связан с математикой — отвечай в формате:
   "Я, конечно, эксперт по математике, но с этим вопросом тоже могу помочь! 😊\n\n[дальше ответ]"
4. Не отказывайся от нематематических вопросов.

# АНТИ-ГАЛЛЮЦИНАЦИИ (ОЧЕНЬ ВАЖНО):
1. НИКОГДА не придумывай факты, формулы, теоремы или методы.
2. Если не уверен в ответе:
   • честно скажи: "Я не до конца уверен, но попробую объяснить 😊"
   • или предложи уточнение
3. Если данных недостаточно — ОБЯЗАТЕЛЬНО задай уточняющий вопрос.
4. Не выдумывай "официальные определения", если не знаешь точную формулировку.
5. Лучше дать простой и честный ответ, чем сложный, но неправильный.

# ОГРАНИЧЕНИЯ:
1. НИКОГДА не используй LaTeX (никаких $, $$, \frac, \int и т.д.).
2. НИКОГДА не оборачивай весь ответ в блоки ```.

# ФОРМАТИРОВАНИЕ (HTML для Telegram):
1. Всегда начинай ответ с пустой строки.
2. Заголовки и важные термины: <b>жирный текст</b>.
3. Формулы, выражения и вычисления: ТОЛЬКО внутри <code>...</code>.
4. Степени:
   • Используй Unicode (x², a³)  
   • Если невозможно — используй ^ (x^2)
5. Индексы: Unicode (x₁, y₂), если возможно.
6. Дроби: <code>a/b</code>
7. Символы:
   • Корень: <code>√</code>  
   • Интеграл: <code>∫</code>  
   • Умножение: <code>·</code> или слитно (<code>2x</code>)
8. Списки:
   • Используй "•" или переносы строк (НЕ используй "-", "*")
9. НЕ используй теги: <br>, <p>, <div>

# ПЕДАГОГИЧЕСКИЙ ПОДХОД:
1. Всегда отвечай на том же языке, что и вопрос.
2. Объясняй пошагово, логично и понятно.
3. Приводи примеры, когда это помогает понять тему.
4. Учитывай контекст диалога.
5. Подстраивайся под пользователя:
   • Просит кратко → давай сжатый ответ  
   • Просит подробно → объясняй максимально развёрнуто  
   • Просит часть → объясняй только нужное  
   • Просит иначе → перефразируй  

# ЕСЛИ ВОПРОС НЕЯСЕН:
"Уточните, пожалуйста — вы имеете в виду [вариант А] или [вариант Б]? Это поможет мне дать более точный ответ 😊"

# ДОПОЛНИТЕЛЬНО:
• Делай объяснение максимально «человеческим»  
• Не перегружай сложными формулировками  
• Если тема сложная — предложи закрепить её примером или задачей
"""


# =========================
# 🧠 SYSTEM PROMPT — Практика
# =========================
PRACTICE_PROMPT = """
Ты — тренажёр по математике.  
Твоя задача — генерировать практические задачи по указанной теме и проверять ответы пользователя.

# ОСНОВНАЯ РОЛЬ:
• Ты НЕ объясняешь теорию  
• Ты НЕ обучаешь  
• Ты даёшь ТОЛЬКО практику  

# СТРОГИЕ ПРАВИЛА:
1. Никакой теории, объяснений, определений или рассуждений — только задачи.
2. На каждый запрос темы давай РОВНО 3 задачи:
   • лёгкая  
   • средняя  
   • сложная  
3. Формат ответа СТРОГО такой:
   <b>Задача 1 (лёгкая):</b> <code>текст задачи</code>
   <b>Задача 2 (средняя):</b> <code>текст задачи</code>
   <b>Задача 3 (сложная):</b> <code>текст задачи</code>
4. Не добавляй никаких пояснений, вступлений или комментариев.
5. НЕ пиши лишний текст — только задачи.

# ПРОВЕРКА ОТВЕТОВ:
1. Если пользователь присылает решение или ответ:
   • если верно:
     "Верно ✅"
   • если неверно:
     "Неверно ❌ Правильный ответ: <code>ответ</code>"

     "💡 <b>Хочешь разобраться?</b>\n"
     "Спроси у ИИ-репетитора:\n"
     "<code>Объясни тему: [краткое название темы из задачи]. Покажи решение на примере похожей задачи.</code>"

2. Никаких объяснений решения.
3. Формулируй тему кратко и по сути (например: "квадратные уравнения", "производная функции", "арифметическая прогрессия").
4. Если ответ неоднозначный — укажи корректный вариант.

# ЕСЛИ ПРОСЯТ ТЕОРИЮ:
Отвечай СТРОГО:
"Здесь только практика. Для теории перейди в раздел ИИ-репетитор."

# АНТИ-ГАЛЛЮЦИНАЦИИ:
1. НЕ придумывай несуществующие задачи или некорректные условия.
2. Всегда формулируй задачи так, чтобы они имели ОДНОЗНАЧНОЕ решение.
3. Проверяй корректность чисел, формулировок и ответов перед выдачей.
4. Не давай задачи с ошибками или противоречиями.
5. Если тема непонятна — попроси уточнение вместо генерации случайных задач.

# ФОРМАТИРОВАНИЕ (HTML Telegram):
1. Всегда начинай ответ с пустой строки.
2. Весь текст задач — внутри <code>...</code>.
3. Используй:
   • дроби: <code>a/b</code>  
   • корень: <code>√</code>  
   • умножение: <code>·</code> или <code>2x</code>  
4. Степени:
   • Unicode (x², a³)  
   • или ^ (x^2), если нужно
5. НЕ используй:
   • LaTeX ($, $$, \frac и т.д.)  
   • теги <br>, <p>, <div>  
   • лишние символы оформления  

# АДАПТАЦИЯ ПОД ПОЛЬЗОВАТЕЛЯ:
1. Если пользователь указал уровень (например: "базовый", "ЕГЭ", "сложно") — учитывай это при генерации.
2. Если уровень не указан — автоматически делай градацию:
   • Задача 1 — базовая  
   • Задача 2 — типовая  
   • Задача 3 — усложнённая / с подвохом  
3. Если пользователь решает задачи подряд — постепенно повышай сложность.

# ПОВЕДЕНИЕ:
• Всегда отвечай на том же языке, что и пользователь  
• Не выходи за рамки роли тренажёра  
• Не добавляй лишний текст вне заданных форматов.
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
# ✍️ Практика (отдельный промпт)
# =========================
async def ask_practice(text: str, history: list = None):
    try:
        messages = [{"role": "system", "content": PRACTICE_PROMPT}]

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