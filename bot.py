import os
import json
import logging
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я AI-бот. Отправь мне текст, и я отвечу.\n\n"
        "Команды:\n"
        "/start - Начать\n"
        "/image <промпт> - Сгенерировать картинку\n\n"
        "Просто напиши мне что-нибудь, и ИИ ответит!"
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args) if context.args else None

    if not prompt:
        await update.message.reply_text(
            "Используй: /image <описание картинки>\n"
            "Пример: /image кот в космосе"
        )
        return

    await update.message.reply_text("Генерирую картинку...")

    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
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


async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text

    if not user_message:
        return

    await update.message.reply_text("Думаю...")

    try:
        url = "https://keylessai.thryx.workers.dev/v1/chat/completions"
        payload = {
            "model": "openai",
            "messages": [
                {"role": "user", "content": user_message}
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        reply = data["choices"][0]["message"]["content"]

        if len(reply) > 4000:
            reply = reply[:4000] + "..."

        await update.message.reply_text(reply)

    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text(
            "Произошла ошибка при обращении к ИИ. Попробуй позже."
        )


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
