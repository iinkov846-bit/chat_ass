import os
import logging
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update
from openai import AsyncOpenAI

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OWNER_ID_RAW = os.getenv("OWNER_ID")
DEBUG = os.getenv("DEBUG", "0") == "1"

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")

if not BOT_TOKEN or not GROQ_API_KEY or not OWNER_ID_RAW:
    raise ValueError("Задай BOT_TOKEN, GROQ_API_KEY и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

# === НАСТРОЙКИ ===
PERSISTENT_THRESHOLD = 2
CONTEXT_SIZE = 10

message_counter = defaultdict(int)
chat_history = defaultdict(list)

SYSTEM_PROMPT = """Ты — дружелюбный и полезный ассистент. 
Отвечай кратко и по делу на русском языке.
Если не знаешь ответа — честно скажи об этом.
Не выдумывай факты."""


# === ОТЛАДКА ===
@dp.update()
async def debug_all_updates(update: Update):
    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


# === ПОДКЛЮЧЕНИЕ К БИЗНЕС-АККАУНТУ ===
@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def ask_groq(chat_id: int, user_message: str) -> str:
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
        chat_history[chat_id].clear()
        return "⚠️ Извините, сейчас я недоступен. Попробуйте позже."


async def save_message_to_owner(message: Message):
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "без username"
    
    header = (
        "📥 Новое сообщение вам\n"
        f"👤 От: {sender.full_name} ({username})\n"
        f"🆔 ID: {sender.id}"
    )
    
    if message.text:
        await bot.send_message(OWNER_ID, f"{header}\n\n💬 Текст:\n{message.text}")
    else:
        await bot.send_message(OWNER_ID, header)
        try:
            # Для медиа используем copy_message с business_connection_id
            await bot.copy_message(
                chat_id=OWNER_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                business_connection_id=message.business_connection_id
            )
        except Exception as e:
            logging.warning(f"⚠️ Не удалось скопировать медиа: {e}")


# === ОСНОВНОЙ ОБРАБОТЧИК ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    user_text = message.text or ""
    
    if not user_text:
        return
    
    # Пересылаем владельцу
    try:
        await save_message_to_owner(message)
    except Exception as e:
        logging.error(f"❌ Не удалось переслать владельцу: {e}")
    
    # Увеличиваем счётчик
    message_counter[chat_id] += 1
    
    # Первое сообщение — шаблонный ответ
    if message_counter[chat_id] == 1:
        # Отправляем временное сообщение (business_connection_id подставляется автоматически)
        temp_msg = await message.answer("⏳ Обработка...")
        
        await asyncio.sleep(1.5)
        
        # Удаляем через delete_business_messages (правильный метод для бизнес-чатов)
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                chat_id=chat_id,
                message_ids=[temp_msg.message_id]
            )
        except Exception as e:
            logging.warning(f"⚠️ Не удалось удалить временное сообщение: {e}")
        
        # Отправляем финальное
        await message.answer("✅ Ваше сообщение было доставлено, ожидайте ответ.")
        
        logging.info(f"📨 Шаблонный ответ для {sender_name}")
    
    # Повторные сообщения — подключаем ИИ
    else:
        temp_msg = await message.answer("⏳ Думаю...")
        reply = await ask_groq(chat_id, user_text)
        
        # Редактируем через edit_message_text с business_connection_id
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text=reply,
            business_connection_id=message.business_connection_id
        )
        logging.info(f"🤖 Groq (Qwen) ответил {sender_name}")


# === ЕСЛИ ВЛАДЕЛЕЦ САМ ОТВЕТИЛ — СБРАСЫВАЕМ СЧЁТЧИК ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    if getattr(message, "sender_business_bot", None) is not None:
        return
    chat_id = message.chat.id
    message_counter[chat_id] = 0
    chat_history[chat_id].clear()
    logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — счётчик сброшен")


# === ЗАПУСК ===
async def main():
    logging.info("🚀 Запуск бизнес-бота с Groq (Qwen3-32B)...")
    logging.info(f"🧠 Модель: {GROQ_MODEL}")
    logging.info(f"👑 Владелец: {OWNER_ID}")
    
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
