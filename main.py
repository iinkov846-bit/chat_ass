import os
import logging
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection
from openai import AsyncOpenAI

# Настраиваем логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([BOT_TOKEN, OWNER_ID, OPENAI_API_KEY]):
    raise ValueError("Ошибка: Не все переменные окружения заданы в Railway!")

# Инициализация клиентов
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# === НАСТРОЙКИ ПОВЕДЕНИЯ БОТА ===
PERSISTENT_THRESHOLD = 2
CONTEXT_HISTORY_SIZE = 10
TRIGGER_WORDS = {"ну", "алло", "ты тут", "ответь", "hello", "are you there", "ты здесь", "ау"}

# === ХРАНИЛИЩА В ПАМЯТИ ===
# Используем chat_id как ключ (в ЛС chat_id == user_id)
message_counter = defaultdict(int)
chat_history = defaultdict(list)

# Системный промпт для GPT
SYSTEM_PROMPT = """Ты — личный ассистент владельца этого Telegram-аккаунта. 
Отвечай от первого лица ("я"), как будто ты — это он сам.
Стиль: дружелюбный, краткий, естественный, как в обычной переписке.
НИКОГДА не упоминай, что ты ИИ, языковая модель или бот.
Если спрашивают, кто ты — отвечай уклончиво: "Просто занят сейчас, отвечу позже".
Если собеседник настойчив — вежливо пообещай ответить в течение дня."""


# === 1. Подключение бота к аккаунту ===
@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name}")


# === 2. Вспомогательные функции ===
def is_persistent(text: str) -> bool:
    """Проверяет, содержит ли сообщение слова-маркеры настойчивости."""
    if not text:
        return False
    text_lower = text.lower()
    return any(word in text_lower for word in TRIGGER_WORDS)


async def ask_gpt(chat_id: int, user_name: str, new_message: str) -> str:
    """Отправляет запрос в ChatGPT с учётом истории переписки."""
    chat_history[chat_id].append({"role": "user", "content": new_message})
    history = chat_history[chat_id][-CONTEXT_HISTORY_SIZE:]
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Имя собеседника: {user_name}. Отвечай ему лично."}
    ] + history
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        chat_history[chat_id].append({"role": "assistant", "content": reply})
        return reply
        
    except Exception as e:
        logging.error(f"❌ Ошибка OpenAI API: {e}")
        return "Я сейчас очень занят, но обязательно отвечу тебе чуть позже! 🙏"


# === 3. Обработчик сообщений ОТ ВЛАДЕЛЬЦА (сброс счётчика) ===
@dp.message(F.business_connection_id & F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    """Если владелец сам пишет собеседнику — сбрасываем счётчик настойчивости."""
    chat_id = message.chat.id
    if chat_id in message_counter:
        message_counter[chat_id] = 0
        chat_history[chat_id].clear()
        logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — бот замолкает")


# === 4. Основной обработчик входящих сообщений ===
@dp.message(F.business_connection_id & (F.from_user.id != OWNER_ID))
async def handle_business_message(message: Message):
    """Обрабатывает сообщения от других пользователей."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    sender_name = message.from_user.first_name or "Друг"
    text = message.text or ""
    
    try:
        # ШАГ 1: Отправляем индикатор "Обрабатываю..."
        temp_message = await message.answer(
            text="⏳ Обрабатываю...",
            business_connection_id=message.business_connection_id
        )
        
        # ШАГ 2: Копируем сообщение владельцу (защита от удаления)
        await bot.copy_message(
            chat_id=OWNER_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            business_connection_id=message.business_connection_id
        )
        
        # ШАГ 3: Обновляем счётчик сообщений от этого пользователя
        message_counter[chat_id] += 1
        
        # ШАГ 4: Определяем, нужен ли GPT
        use_gpt = (message_counter[chat_id] >= PERSISTENT_THRESHOLD) or is_persistent(text)
        
        if use_gpt:
            await asyncio.sleep(1.5)
            gpt_reply = await ask_gpt(chat_id, sender_name, text)
            
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=temp_message.message_id,
                text=gpt_reply,
                business_connection_id=message.business_connection_id
            )
            logging.info(f"🤖 GPТ ответил {sender_name}: {gpt_reply[:50]}...")
        else:
            await asyncio.sleep(1)
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=temp_message.message_id,
                text=f"✅ {sender_name}, ваше сообщение получено. Я скоро отвечу!",
                business_connection_id=message.business_connection_id
            )
            logging.info(f"📨 Стандартный ответ для {sender_name}")
            
    except Exception as e:
        logging.error(f"❌ Ошибка при обработке сообщения: {e}")


async def main():
    logging.info("🚀 Запуск персонального бизнес-бота с интеграцией ChatGPT...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
