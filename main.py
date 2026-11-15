import os
import json
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
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b") # Или qwen/qwen3.8-27b

if not BOT_TOKEN or not GROQ_API_KEY or not OWNER_ID_RAW:
    raise ValueError("Задай BOT_TOKEN, GROQ_API_KEY и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)
MUTED_FILE = "muted_users.json"

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


# === УПРАВЛЕНИЕ СПИСКОМ ОТКЛЮЧЕННЫХ ОТВЕТОВ ===
def load_muted_users() -> dict:
    if os.path.exists(MUTED_FILE):
        try:
            with open(MUTED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_muted_users(muted_dict: dict):
    with open(MUTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(muted_dict, f, ensure_ascii=False, indent=2)


# === ОТЛАДКА ===
@dp.update()
async def debug_all_updates(update: Update):
    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


# === КОМАНДЫ УПРАВЛЕНИЯ (ТОЛЬКО ДЛЯ ВЛАДЕЛЬЦА) ===
@dp.message(F.text.startswith("/reply"))
@dp.business_message(F.text.startswith("/reply"))
async def cmd_reply(message: Message):
    if message.from_user.id != OWNER_ID:
        return  # Игнорируем, если не владелец
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "📋 **Управление автоответами:**\n\n"
            "/reply <user_id> — переключить статус (Вкл/Выкл)\n"
            "/reply list — показать список отключенных\n\n"
            "💡 *ID пользователя можно взять из пересланного сообщения.*",
            parse_mode="Markdown"
        )
        return

    if parts[1].lower() == "list":
        muted = load_muted_users()
        if not muted:
            await message.answer("✅ Автоответы **включены** для всех пользователей. Список пуст.")
        else:
            text = "🚫 **Автоответы ОТКЛЮЧЕНЫ для:**\n\n"
            for uid, name in muted.items():
                text += f"• `{uid}` — {name}\n"
            await message.answer(text, parse_mode="Markdown")
        return

    target_id_str = parts[1]
    if not target_id_str.isdigit():
        await message.answer("❌ Ошибка: ID должен состоять только из цифр.")
        return

    target_id = int(target_id_str)
    muted = load_muted_users()
    str_id = str(target_id)

    if str_id in muted:
        # Если уже в списке — удаляем (включаем ответы)
        name = muted.pop(str_id)
        save_muted_users(muted)
        await message.answer(f"✅ Автоответы для **{name}** (`{target_id}`) теперь **ВКЛЮЧЕНЫ**.")
    else:
        # Если нет в списке — добавляем (выключаем ответы)
        try:
            chat = await bot.get_chat(target_id)
            name = chat.full_name or "Неизвестный пользователь"
        except Exception:
            name = "Неизвестный (нет доступа к профилю)"
        
        muted[str_id] = name
        save_muted_users(muted)
        await message.answer(f"🚫 Автоответы для **{name}** (`{target_id}`) теперь **ВЫКЛЮЧЕНЫ**.\nБот будет только пересылать его сообщения.")


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
async def ask_groq(chat_id: int, user_message: str) -> str:
    chat_history[chat_id].append({"role": "user", "content": user_message})
    history = chat_history[chat_id][-CONTEXT_SIZE:]
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    
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
    
    # 1. ВСЕГДА пересылаем сообщение владельцу
    try:
        await save_message_to_owner(message)
    except Exception as e:
        logging.error(f"❌ Не удалось переслать владельцу: {e}")
    
    # 2. Проверяем, отключены ли автоответы для этого пользователя
    muted = load_muted_users()
    if str(chat_id) in muted:
        logging.info(f"🔇 Автоответ отключен для {sender_name} ({chat_id}), только пересылка")
        return  # Прерываем функцию, бот НЕ будет отвечать

    # 3. Логика автоответов (если не в списке muted)
    message_counter[chat_id] += 1
    
    if message_counter[chat_id] == 1:
        temp_msg = await message.answer("⏳ Обработка...")
        await asyncio.sleep(1.5)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text="✅ Ваше сообщение было доставлено, ожидайте ответ.",
            business_connection_id=message.business_connection_id
        )
        logging.info(f"📨 Шаблонный ответ для {sender_name}")
    else:
        temp_msg = await message.answer("⏳ Думаю...")
        reply = await ask_groq(chat_id, user_text)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text=reply,
            business_connection_id=message.business_connection_id
        )
        logging.info(f"🤖 ИИ ответил {sender_name}")


# === СБРОС СЧЁТЧИКА, ЕСЛИ ВЛАДЕЛЕЦ ОТВЕТИЛ САМ ===
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
    logging.info("🚀 Запуск бизнес-бота с Groq и управлением автоответами...")
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
