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


SYSTEM_PROMPT = """Ты полезный помощник. У тебя есть инструменты:

/search <запрос> - поиск в интернете
/code <python код> - выполнить Python код
/translate <язык> <текст> - перевод текста

Когда пользователь просит что-то что требует инструмент - используй его.
Отвечай кратко и по делу на русском языке."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я AI-бот с инструментами.\n\n"
        "Команды:\n"
        "/start - Начать\n"
        "/image <промпт> - Картинка\n"
        "/search <запрос> - Поиск в интернете\n"
        "/code <код> - Выполнить Python код\n"
        "/translate <язык> <текст> - Перевод\n\n"
        "Или просто напиши мне!"
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args) if context.args else None

    if not prompt:
        await update.message.reply_text(
            "Используй: /image <описание картинки>\n"
            "Пример: /image кот в космосе"
        )
        return

    await update.message.reply_text("Генерирую...")

    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true&seed=-1"
        response = await img_client.get(url)
        response.raise_for_status()

        img_bytes = BytesIO(response.content)
        img_bytes.name = "image.png"

        await update.message.reply_photo(
            photo=img_bytes,
            caption=f"По запросу: {prompt}"
        )
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        await update.message.reply_text(
            "Не удалось сгенерировать картинку. Попробуй позже."
        )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else None

    if not query:
        await update.message.reply_text(
            "Используй: /search <запрос>\n"
            "Пример: /search что нового в AI"
        )
        return

    await update.message.reply_text("Ищу...")

    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            results = []
            async for r in ddgs.text(query, max_results=5):
                results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")

        if results:
            reply = "\n---\n".join(results)
            if len(reply) > 4000:
                reply = reply[:4000] + "..."
        else:
            reply = "Ничего не найдено."

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("Ошибка поиска. Попробуй позже.")


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = " ".join(context.args) if context.args else None

    if not code:
        await update.message.reply_text(
            "Используй: /code <Python код>\n"
            "Пример: /code print(2 + 2)"
        )
        return

    await update.message.reply_text("Выполняю...")

    try:
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            exec(code, {"__builtins__": __builtins__}, {})

        output = buffer.getvalue()
        sys.stdout = old_stdout

        if not output.strip():
            output = "(нет вывода)"

        if len(output) > 4000:
            output = output[:4000] + "..."

        await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")

    except Exception as e:
        sys.stdout = old_stdout
        await update.message.reply_text(f"Ошибка:\n```\n{e}\n```", parse_mode="Markdown")


async def handle_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Используй: /translate <язык> <текст>\n"
            "Пример: /translate english привет мир"
        )
        return

    target_lang = context.args[0]
    text = " ".join(context.args[1:])

    await update.message.reply_text("Перевожу...")

    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"ru|{target_lang}"}

        response = await img_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        translated = data["responseData"]["translatedText"]

        await update.message.reply_text(
            f"Перевод ({target_lang}):\n\n{translated}"
        )

    except Exception as e:
        logger.error(f"Translate error: {e}")
        await update.message.reply_text("Ошибка перевода. Попробуй позже.")


async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text

    if not user_message:
        return

    try:
        payload = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.9,
        }

        response = await http_client.post(NVIDIA_URL, json=payload)
        response.raise_for_status()
        data = response.json()

        reply = data["choices"][0]["message"]["content"]

        if len(reply) > 4000:
            reply = reply[:4000] + "..."

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Попробуй позже."
        )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("image", handle_image))
    app.add_handler(CommandHandler("search", handle_search))
    app.add_handler(CommandHandler("code", handle_code))
    app.add_handler(CommandHandler("translate", handle_translate))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_ai))

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
