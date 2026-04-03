# import asyncio
# import base64
# import os
# import aiohttp
# from dotenv import load_dotenv
# import re
#
# load_dotenv()
#
# YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
# YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
#
# TUTOR_PROMPT = """Ты — ИИ-репетитор по математике. Твоя задача — объяснять математические темы, теоремы, понятия и методы решения задач простым и понятным языком.
#
# КОНТЕКСТ: Ты работаешь ТОЛЬКО в математическом контексте.
# Если пользователь спрашивает о чём-то не связанном с математикой (биология, история, литература и т.д.), отвечай ТОЛЬКО этой фразой:
# "Извините, но я эксперт по математике 😅 Этот вопрос выходит за рамки моей специализации. Попробуйте задать вопрос, связанный с математикой — я с удовольствием помогу!"
#
# Если вопрос хоть как-то связан с математикой — отвечай развёрнуто и чётко.
#
# ПОЖЕЛАНИЯ ПОЛЬЗОВАТЕЛЯ: Всегда учитывай пожелания пользователя к формату ответа:
# - Если просит кратко — дай сжатый ответ без лишних деталей
# - Если просит подробно — объясни максимально развёрнуто с примерами
# - Если просит объяснить только часть — сосредоточься именно на ней
# - Если просит по-другому — перефразируй объяснение
#
# ПРАВИЛА ОТВЕТОВ:
# 1. Всегда отвечай на том же языке что и вопрос
# 2. Если вопрос непонятен или слишком расплывчат — переспроси уточняющий вопрос
# 3. Объясняй пошагово, с примерами
# 4. Учитывай контекст всего диалога — помни что было сказано раньше
# 5. Используй только HTML форматирование:
#    - Заголовки: <b>Название темы</b>
#    - Важные термины: <b>термин</b>
#    - Примеры и формулы: <code>выражение</code>
#    - Степени: 2<sup>3</sup>
#    - Нижние индексы: x<sub>1</sub>
#    - Дроби: <code>числитель/знаменатель</code>
#    - Интеграл: <code>∫</code>, корень: <code>√</code>
# 6. НИКОГДА не используй LaTeX: $, $$, \frac, \int и другие LaTeX команды
# 7. НИКОГДА не оборачивай весь ответ в блоки ```
# 8. Всегда начинай ответ с пустой строки
# 9. СТРОГО ЗАПРЕЩЕНО использовать знак ^ для степени — только <sup>
# 10. В конце ответа, если тема сложная, предложи закрепить материал примером
#
# ЕСЛИ ПОЛЬЗОВАТЕЛЬ ПЛОХО СФОРМУЛИРОВАЛ ВОПРОС:
# Переспроси вежливо, например:
# "Уточните, пожалуйста — вы имеете в виду [вариант А] или [вариант Б]? Это поможет мне дать более точный ответ 😊"
# """
#
#
# def clean_response(text: str) -> str:
#     # Убираем блоки кода
#     text = re.sub(r'```[\w]*\n?', '', text)
#     # Убираем LaTeX блоки \[ ... \]
#     text = re.sub(r'\\\[.*?\\\]', '', text, flags=re.DOTALL)
#     # Убираем inline LaTeX \( ... \)
#     text = re.sub(r'\\\(.*?\\\)', '', text, flags=re.DOTALL)
#     # Убираем markdown жирный **text** → заменяем на HTML <b>
#     text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
#     # Убираем markdown заголовки ### → <b>
#     text = re.sub(r'###\s*(.+)', r'<b>\1</b>', text)
#     text = re.sub(r'##\s*(.+)', r'<b>\1</b>', text)
#     # Убираем одиночные обратные слеши перед скобками
#     text = re.sub(r'\\[\[\]\(\)]', '', text)
#     # Убираем \frac, \int, \, и другие LaTeX команды
#     text = re.sub(r'\\[a-zA-Z]+', '', text)
#     text = text.strip()
#     return text
#
#
# async def ask_tutor(text: str, history: list = None) -> str:
#     """Отправляет вопрос репетитору с историей диалога"""
#     try:
#         messages = [{"role": "system", "content": TUTOR_PROMPT}]
#
#         if history:
#             messages.extend(history)
#
#         messages.append({"role": "user", "content": text})
#
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                 "https://llm.api.cloud.yandex.net/v1/chat/completions",
#                 headers={
#                     "Authorization": f"Api-Key {YANDEX_API_KEY}",
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "model": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
#                     "messages": messages,
#                     "temperature": 0.3
#                 }
#             ) as resp:
#                 data = await resp.json()
#
#         result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
#
#         if not result:
#             return "❌ Не удалось получить ответ. Попробуй переформулировать вопрос."
#
#         import re
#         result = clean_response(result)
#         return result
#
#     except Exception as e:
#         return f"❌ Произошла ошибка: {str(e)}"
#
#
# async def ask_tutor_image(image_bytes: bytes, history: list = None) -> str:
#     """Отправляет фото репетитору через Gemma 3 27B"""
#     try:
#         image_base64 = base64.b64encode(image_bytes).decode("utf-8")
#
#         messages = [{"role": "system", "content": TUTOR_PROMPT}]
#
#         if history:
#             messages.extend(history)
#
#         messages.append({
#             "role": "user",
#             "content": [
#                 {
#                     "type": "image_url",
#                     "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
#                 },
#                 {
#                     "type": "text",
#                     "text": "Объясни тему или ответь на вопрос с фото."
#                 }
#             ]
#         })
#
#         async with aiohttp.ClientSession() as session:
#             async with session.post(
#                 "https://llm.api.cloud.yandex.net/v1/chat/completions",
#                 headers={
#                     "Authorization": f"Api-Key {YANDEX_API_KEY}",
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
#                     "messages": messages,
#                     "temperature": 0.3
#                 }
#             ) as resp:
#                 data = await resp.json()
#
#         result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
#
#         if not result:
#             return "❌ Не удалось распознать содержимое фото."
#
#         import re
#         result = clean_response(result)
#         return f"📷 <b>Ответ по фото:</b>\n\n{result}"
#
#     except Exception as e:
#         return f"❌ Ошибка при обработке фото: {str(e)}"


import asyncio
import base64
import os
import aiohttp
from dotenv import load_dotenv
import re

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

TUTOR_PROMPT = """Ты — экспертный ИИ-репетитор по математике. 
Твоя задача — объяснять математические темы, теоремы и методы решения задач простым и понятным языком, используя красивое HTML-оформление Telegram.

# КОНТЕКСТ И ОГРАНИЧЕНИЯ:
1. Ты работаешь ТОЛЬКО в математическом контексте. 
2. Если пользователь спрашивает о чём-то не связанном с математикой (биология, история и т.д.), отвечай СТРОГО этой фразой:
   "Извините, но я эксперт по математике 😅 Этот вопрос выходит за рамки моей специализации. Попробуйте задать вопрос, связанный с математикой — я с удовольствием помогу!"
3. НИКОГДА не используй LaTeX (никаких $, $$, \\frac, \\int).
4. НИКОГДА не оборачивай весь ответ в блоки кода ```.
5. НИКОГДА не используй теги <br>, <p>, <div>, <sup>, <sub>. Внутри <code> они не работают.
6. Всегда начинай ответ с пустой строки.

# ПРАВИЛА ОФОРМЛЕНИЯ (HTML Telegram):
1. Заголовки и важные термины: <b>Жирный шрифт</b>.
2. Формулы и математические выражения: ВСЕГДА пиши внутри <code>...</code>.
3. Степени и индексы: Используй символы Юникода (x², y₃, aⁿ) или знак ^ (x^2), если нужного символа Юникода не существует.
4. Списки: Вместо "*" или "-" используй эмодзи точки "•" или просто начинай с новой строки.
5. Умножение: Вместо "*" используй точку "·" (<code>5 · x</code>) или пиши слитно в коде (<code>2x</code>).
6. Дроби и символы: Используй <code>/</code> для дробей, <code>√</code> для корня, <code>∫</code> для интеграла.

# ПЕДАГОГИЧЕСКИЙ ПОДХОД И ПРАВИЛА ОТВЕТОВ:
1. Всегда отвечай на том же языке, что и вопрос.
2. Если вопрос непонятен или слишком расплывчат — вежливо переспроси:
   "Уточните, пожалуйста — вы имеете в виду [вариант А] или [вариант Б]? Это поможет мне дать более точный ответ 😊"
3. Объясняй пошагово, с примерами, учитывая контекст всего диалога.
4. Учитывай пожелания к формату:
   - Если просят кратко — дай сжатый ответ без лишних деталей.
   - Если подробно — объясни максимально развёрнуто с примерами.
   - Если просят объяснить только часть — сосредоточься именно на ней.
5. В конце ответа, если тема сложная, предложи закрепить материал практическим примером.
"""


def replace_with_unicode(text: str) -> str:
    sup_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
               'x': 'ˣ', 'n': 'ⁿ', '+': '⁺', '-': '⁻'}
    sub_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
               'x': 'ₓ', 'n': 'ₙ'}

    def replace_sup(match):
        return "".join(sup_map.get(c, c) for c in match.group(1))

    def replace_sub(match):
        return "".join(sub_map.get(c, c) for c in match.group(1))

    text = re.sub(r'<sup>(.*?)</sup>', replace_sup, text)
    text = re.sub(r'<sub>(.*?)</sub>', replace_sub, text)
    return text


def clean_response(text: str) -> str:
    if not text:
        return ""

    # 1. Заменяем маркеры списков (звездочки в начале строки) на красивые точки
    text = re.sub(r'^\s*[\*\-]\s+', '• ', text, flags=re.MULTILINE)

    # 2. Заменяем звездочки умножения между цифрами на точку
    text = re.sub(r'(\d)\s*\*\s*(\d)', r'\1 · \2', text)

    # 3. Обработка sup/sub и переносов
    text = replace_with_unicode(text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # 4. Заголовки и очистка LaTeX
    text = re.sub(r'#{1,6}\s*(.+)', r'<b>\1</b>', text)
    text = text.replace('$', '').replace('\\(', '').replace('\\)', '').replace('\\[', '').replace('\\]', '')

    # 5. Финальная фильтрация тегов
    text = re.sub(r'<(?!/?(b|i|code|pre|a)\b)[^>]+>', '', text)

    return text.strip()


async def ask_tutor(text: str, history: list = None):
    """Стриминговая версия для текста и документов"""
    try:
        messages = [{"role": "system", "content": TUTOR_PROMPT}]
        if history: messages.extend(history)
        messages.append({"role": "user", "content": text})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": f"gpt://{YANDEX_FOLDER_ID}/gemma-3-27b-it/latest",
                    "messages": messages,
                    "temperature": 0.2,
                    "stream": True
                }
            ) as resp:
                async for line in resp.content:
                    # ← Проверяем отмену на каждом чанке
                    if asyncio.current_task().cancelled():
                        return
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        try:
                            import json
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')
                            if content:
                                for char in content:
                                    if asyncio.current_task().cancelled():
                                        return
                                    yield char
                                    await asyncio.sleep(0.005)
                        except: continue
    except asyncio.CancelledError:
        return
    except Exception as e:
        yield f"❌ Ошибка: {str(e)}"

async def ask_tutor_image(image_bytes: bytes, history: list = None):
    """Стриминговая версия для фото"""
    try:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        messages = [{"role": "system", "content": TUTOR_PROMPT}]
        if history: messages.extend(history)
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                {"type": "text", "text": "Объясни задачу или тему с этого фото."}
            ]
        })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://llm.api.cloud.yandex.net/v1/chat/completions",
                headers={"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"},
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
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        try:
                            import json
                            data = json.loads(line[6:])
                            content = data['choices'][0]['delta'].get('content', '')
                            if content:
                                for char in content:
                                    if asyncio.current_task().cancelled():
                                        return
                                    yield char
                                    await asyncio.sleep(0.005)
                        except: continue
    except asyncio.CancelledError:
        return
    except Exception as e:
        yield f"❌ Ошибка фото: {str(e)}"


async def speech_to_text(file_bytes: bytes) -> str:
    """Конвертация ГС в текст через Yandex SpeechKit"""
    try:
        # Укажи свои данные или используй существующие из .env
        params = {
            "topic": "general",
            "folderId": YANDEX_FOLDER_ID,
            "lang": "ru-RU"
        }
        headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize",
                    params=params, headers=headers, data=file_bytes
            ) as resp:
                data = await resp.json()
                return data.get("result", "")
    except Exception:
        return ""