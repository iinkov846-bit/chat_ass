import os
import logging
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from openai import AsyncOpenAI

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OWNER_ID_RAW = os.getenv("OWNER_ID")

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")

if not BOT_TOKEN or not GROQ_API_KEY or not OWNER_ID_RAW:
    raise ValueError("Задай BOT_TOKEN, GROQ_API_KEY и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# OpenAI-совместимый клиент для Groq
openai_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

# === НАСТРОЙКИ ===
PERSISTENT_THRESHOLD = 2  # Со скольки сообщений включать ИИ
CONTEXT_SIZE = 10         # Сколько сообщений помнить для контекста

# Хранилища
message_counter = defaultdict(int)
chat_history = defaultdict(list)

# Системный промпт для Qwen через Groq
SYSTEM_PROMPT = """Ты — дружелюбный и полезный ассистент. 
Отвечай кратко и по делу на русском языке.
Если не знаешь ответа — честно скажи об этом.
Не выдумывай факты."""


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def ask_groq(chat_id: int, user_message: str) -> str:
    """Отправляет запрос в Groq (Qwen3-32B) с учётом истории. При ошибке — fallback."""
    chat_history[chat_id].append({"role": "user", "content": user_message})
    history = chat_history[chat_id][-CONTEXT_SIZE:]
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ] + history
    
    try:
        response = await openai_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        chat_history[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logging.error(f"❌ Ошибка Groq API: {e}")
        # Сбрасываем историю при ошибке, чтобы не копилась
        chat_history[chat_id].clear()
        return "⚠️ Извините, сейчас я недоступен. Попробуйте позже."


async def save_message_to_owner(message: Message):
    """Пересылает сообщение владельцу бота."""
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "без username"
    
    header = (
        "📥 Новое сообщение боту\n"
        f"👤 От: {sender.full_name} ({username})\n"
        f"🆔 ID: {sender.id}"
    )
    
    if message.text:
        await bot.send_message(OWNER_ID, f"{header}\n\n💬 Текст:\n{message.text}")
    else:
        # Для медиа отправляем заголовок + копируем сообщение
        await bot.send_message(OWNER_ID, header)
        try:
            await bot.copy_message(OWNER_ID, message.chat.id, message.message_id)
        except Exception as e:
            logging.warning(f"⚠️ Не удалось скопировать медиа: {e}")


# === ОБРАБОТЧИК СООБЩЕНИЙ ===

@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id
    user_text = message.text or ""
    
    if not user_text:
        return  # Игнорируем пустые/медиа сообщения
    
    # Пересылаем сообщение владельцу
    try:
        await save_message_to_owner(message)
    except Exception as e:
        logging.error(f"❌ Не удалось переслать владельцу: {e}")
    
    # Увеличиваем счётчик
    message_counter[chat_id] += 1
    
    # Первое сообщение — шаблонный ответ
    if message_counter[chat_id] == 1:
        temp_msg = await message.answer("⏳ Обработка...")
        await asyncio.sleep(1.5)
        await bot.delete_message(chat_id, temp_msg.message_id)
        await message.answer("✅ Ваше сообщение было доставлено, ожидайте ответ.")
        logging.info(f"📨 Шаблонный ответ для пользователя {chat_id}")
    
    # Повторные сообщения — подключаем ИИ
    else:
        temp_msg = await message.answer("⏳ Думаю...")
        reply = await ask_groq(chat_id, user_text)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text=reply
        )
        logging.info(f"🤖 Groq (Qwen) ответил пользователю {chat_id}")


# === ЗАПУСК ===

async def main():
    logging.info("🚀 Запуск бота с Groq (Qwen3-32B)...")
    logging.info(f"🧠 Модель: {GROQ_MODEL}")
    logging.info(f"🔗 Эндпоинт: {GROQ_BASE_URL}")
    logging.info(f"👑 Владелец: {OWNER_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
