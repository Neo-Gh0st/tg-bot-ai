import os
import io
import sys
import json
import logging
import contextlib
import httpx
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_KEY = "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"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

http_client = httpx.AsyncClient(timeout=30.0, headers={
    "Authorization": f"Bearer {NVIDIA_KEY}",
    "Content-Type": "application/json",
})

img_client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)


def detect_tool(text: str) -> dict:
    lower = text.lower()

    code_triggers = ["напиши код", "код для", "сделай код", "программа на python",
                     "запусти код", "выполни код", "рассчитай", "посчитай",
                     "сколько будет", "вычисли", "math", "калькулятор"]
    for t in code_triggers:
        if t in lower:
            return {"tool": "code", "query": text}

    search_triggers = ["найди в интернете", "поищи", "что такое", "какой",
                       "какая", "какие", "новости", "погода", "где находится",
                       "кто такой", "что сейчас", "расскажи о", "что происходить",
                       "последние новости", "что нового", "google", "найти информацию"]
    for t in search_triggers:
        if t in lower:
            return {"tool": "search", "query": text}

    translate_triggers = ["переведи", "перевод на", "как будет на", "translate",
                          "как сказать на", "перевести на"]
    for t in translate_triggers:
        if t in lower:
            return {"tool": "translate", "query": text}

    return {"tool": None, "query": text}


async def ai_chat(messages: list, max_tokens: int = 512) -> str:
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.9,
    }
    response = await http_client.post(NVIDIA_URL, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


async def do_search(query: str) -> str:
    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            results = []
            async for r in ddgs.text(query, max_results=5):
                results.append(f"{r['title']}\n{r['href']}\n{r['body']}")

        return "\n\n".join(results) if results else "Ничего не найдено."
    except Exception as e:
        return f"Ошибка поиска: {e}"


async def do_code(code: str) -> str:
    try:
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            exec(code, {"__builtins__": __builtins__}, {})

        output = buffer.getvalue()
        sys.stdout = old_stdout

        return output.strip() if output.strip() else "(нет вывода)"
    except Exception as e:
        sys.stdout = old_stdout
        return f"Ошибка: {e}"


async def do_translate(text: str) -> str:
    try:
        lower = text.lower()
        target = "en"

        lang_map = {"на английский": "en", "на русский": "ru", "на испанский": "es",
                    "на французский": "fr", "на немецкий": "de", "на китайский": "zh",
                    "на японский": "ja", "на корейский": "ko", "на португальский": "pt",
                    "на итальянский": "it", "translate to english": "en",
                    "translate to russian": "ru"}

        for phrase, lang in lang_map.items():
            if phrase in lower:
                target = lang
                break

        clean = text
        for phrase in ["переведи на", "перевод на", "как будет на", "translate to", "перевести на"]:
            clean = clean.replace(phrase, "").replace(phrase.upper(), "")
        clean = clean.strip()

        url = "https://api.mymemory.translated.net/get"
        params = {"q": clean, "langpair": f"ru|{target}"}

        response = await img_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return data["responseData"]["translatedText"]
    except Exception as e:
        return f"Ошибка перевода: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я AI-бот с инструментами.\n\n"
        "Просто напиши мне:\n"
        "- Найди в интернете что-нибудь\n"
        "- Напиши код для чего-нибудь\n"
        "- Переведи на английский привет\n"
        "- Или просто поболтаем!\n\n"
        "/image <промпт> - сгенерировать картинку"
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args) if context.args else None

    if not prompt:
        await update.message.reply_text("Используй: /image <описание>")
        return

    await update.message.reply_text("Генерирую...")

    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true&seed=-1"
        response = await img_client.get(url)
        response.raise_for_status()

        img_bytes = BytesIO(response.content)
        img_bytes.name = "image.png"

        await update.message.reply_photo(photo=img_bytes, caption=f"По запросу: {prompt}")
    except Exception as e:
        logger.error(f"Image error: {e}")
        await update.message.reply_text("Не удалось сгенерировать картинку.")


async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    if not user_message:
        return

    tool_info = detect_tool(user_message)
    tool_result = None

    if tool_info["tool"] == "search":
        await update.message.reply_text("Ищу в интернете...")
        tool_result = await do_search(tool_info["query"])

    elif tool_info["tool"] == "code":
        await update.message.reply_text("Выполняю код...")
        code = user_message
        for phrase in ["напиши код", "код для", "сделай код", "программа на python",
                       "запусти код", "выполни код", "рассчитай", "посчитай",
                       "сколько будет", "вычисли", "math", "калькулятор"]:
            code = code.replace(phrase, "").replace(phrase.upper(), "").strip()
        if not code:
            code = user_message
        tool_result = await do_code(code)

    elif tool_info["tool"] == "translate":
        await update.message.reply_text("Перевожу...")
        tool_result = await do_translate(tool_info["query"])

    try:
        if tool_result:
            messages = [
                {"role": "system", "content": "Ты полезный помощник. Отвечай на русском. Используй результат инструмента для ответа."},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": f"[Результат инструмента]: {tool_result}"},
                {"role": "user", "content": "Сформируй ответ на основе этого результата."}
            ]
        else:
            messages = [
                {"role": "system", "content": "Ты полезный помощник. Отвечай кратко на русском языке."},
                {"role": "user", "content": user_message}
            ]

        reply = await ai_chat(messages)

        if len(reply) > 4000:
            reply = reply[:4000] + "..."

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуй позже.")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("image", handle_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
