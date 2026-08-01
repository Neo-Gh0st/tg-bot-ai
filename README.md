# Telegram AI Bot

Telegram бот с ИИ моделью для ответов на сообщения и генерации изображений.

## Возможности

- Ответы на сообщения с помощью Google Gemini AI
- Генерация изображений по запросу (Pollinations.ai)
- Полностью бесплатно

## Установка

1. Установи Python 3.10+

2. Установи зависимости:
```bash
pip install -r requirements.txt
```

3. Получи API ключи:

**Telegram Bot Token:**
- Открой @BotFather в Telegram
- Создай нового бота командой /newbot
- Скопируй токен

**Google AI API Key:**
- Перейди на https://aistudio.google.com
- Нажми "Get API Key"
- Создай ключ

4. Заполни файл `.env`:
```
TELEGRAM_BOT_TOKEN=твой_токен_бота
GOOGLE_AI_API_KEY=твой_ключ_google
```

5. Запусти бота:
```bash
python bot.py
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и список команд |
| `/image <промпт>` | Генерация изображения |
| Любой текст | Ответ от ИИ |

## Примеры использования

```
/image кот в космосе
/image пейзаж заката в стиле аниме
Привет, как дела?
Объясни квантовую физику простыми словами
```

## Стек

- Python 3.10+
- python-telegram-bot
- Google Gemini AI
- Pollinations.ai
