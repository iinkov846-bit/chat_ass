import os
import logging
import asyncio
import random
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update
from openai import AsyncOpenAI

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (Railway → Variables) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")            # Токен от @BotFather
OWNER_ID = int(os.getenv("OWNER_ID"))         # Ваш Telegram ID
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Ключ OpenAI или Groq
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")            # Необязательно: для Groq
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")   # Модель

if not all([BOT_TOKEN, OWNER_ID, OPENAI_API_KEY]):
    raise ValueError("Ошибка: Не все переменные окружения заданы в Railway!")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Универсальный клиент: работает и с OpenAI, и с Groq (если задан OPENAI_BASE_URL)
client_kwargs = {"api_key": OPENAI_API_KEY}
if OPENAI_BASE_URL:
    client_kwargs["base_url"] = OPENAI_BASE_URL
openai_client = AsyncOpenAI(**client_kwargs)

# === НАСТРОЙКИ ПОВЕДЕНИЯ ===
PERSISTENT_THRESHOLD = 2
CONTEXT_HISTORY_SIZE = 10
TRIGGER_WORDS = {"ну", "алло", "ты тут", "ответь", "hello", "are you there", "ты здесь", "ау"}

message_counter = defaultdict(int)
chat_history = defaultdict(list)

# === ЖЁСТКИЙ ХАРАКТЕР АССИСТЕНТА ===
SYSTEM_PROMPT = """Ты — дерзкий, жёсткий и саркастичный личный ассистент владельца этого Telegram-аккаунта.
Отвечай от первого лица ("я"), как будто ты — это он сам.
Стиль: грубоватый, нетерпеливый, прямолинейный, с сарказмом и чёрным юмором. Без сюсюканий.
Собеседник настойчиво долбит сообщениями — жёстко осади его, дай понять, что он отвлекает.
Отвечай коротко и хлёстко, как в реальной переписке.
НИКОГДА не признавайся, что ты ИИ или бот. Если спрашивают кто ты — огрызайся: "Не твоё дело, я занят".
Будь резким, но без угроз расправы и без оскорблений по национальности, полу и т.п.
Примеры тона: "Чего надо? Я занят. Пиши по делу.", "Ты читать умеешь? Жди, не видишь — занят.", "Ещё раз напишешь 'ну' — вообще отвечать перестану."
"""

# === РАЗНЫЕ ГРУБЫЕ ЗАГЛУШКИ (если API недоступен) ===
FALLBACK_REPLIES = [
    "Я занят. Отвечу, когда освобожусь. Не долби. 😤",
    "Ты глухой? Я сказал — занят. Жди.",
    "Чего надо? Пиши по делу, а не спамь.",
    "Я тебе что, справочная? Подожди, не видишь — занят.",
    "Ещё одно 'ну' — и я вообще отвечать перестану. Жди.",
    "Сейчас не до тебя. Освобожусь — напишу. Всё.",
]


# === ОТЛАДКА (можно удалить после отладки) ===
@dp.update()
async def debug_all_updates(update: Update):
    logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


def is_persistent(text: str) -> bool:
    if not text:
        return False
    return any(word in text.lower() for word in TRIGGER_WORDS)


async def ask_gpt(chat_id: int, user_name: str, new_message: str) -> str:
    chat_history[chat_id].append({"role": "user", "content": new_message})
    history = chat_history[chat_id][-CONTEXT_HISTORY_SIZE:]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Имя собеседника: {user_name}. Отвечай ему лично."}
    ] + history
    try:
        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        chat_history[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logging.error(f"❌ Ошибка API: {e}")
        return random.choice(FALLBACK_REPLIES)


# === СОХРАНЕНИЕ СООБЩЕНИЯ ВЛАДЕЛЬЦУ (независимая копия) ===
async def save_message_to_owner(message: Message):
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "без username"
    header = (
        "📥 Новое сообщение вам\n"
        f"👤 От: {sender.full_name} ({username})\n"
        f"🆔 ID: {sender.id}\n"
        f"💬 Чат: {message.chat.id}"
    )

    if message.text:
        await bot.send_message(OWNER_ID, f"{header}\n\n💬 Текст:\n{message.text}")
        return

    await bot.send_message(OWNER_ID, header)

    if message.photo:
        await bot.send_photo(OWNER_ID, message.photo[-1].file_id, caption=message.caption)
    elif message.video:
        await bot.send_video(OWNER_ID, message.video.file_id, caption=message.caption)
    elif message.voice:
        await bot.send_voice(OWNER_ID, message.voice.file_id, caption=message.caption)
    elif message.audio:
        await bot.send_audio(OWNER_ID, message.audio.file_id, caption=message.caption)
    elif message.document:
        await bot.send_document(OWNER_ID, message.document.file_id, caption=message.caption)
    elif message.animation:
        await bot.send_animation(OWNER_ID, message.animation.file_id, caption=message.caption)
    elif message.sticker:
        await bot.send_sticker(OWNER_ID, message.sticker.file_id)
    elif message.video_note:
        await bot.send_video_note(OWNER_ID, message.video_note.file_id)
    elif message.contact:
        c = message.contact
        await bot.send_contact(OWNER_ID, phone_number=c.phone_number, first_name=c.first_name, last_name=c.last_name)
    elif message.location:
        loc = message.location
        await bot.send_location(OWNER_ID, latitude=loc.latitude, longitude=loc.longitude)
    else:
        await bot.send_message(OWNER_ID, f"⚠️ Сообщение типа '{message.content_type}' не удалось скопировать автоматически.")


@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    if getattr(message, "sender_business_bot", None) is not None:
        return
    chat_id = message.chat.id
    if chat_id in message_counter:
        message_counter[chat_id] = 0
        chat_history[chat_id].clear()
        logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — бот замолкает")


@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    raw_text = message.text or message.caption or ""
    text_for_gpt = raw_text or f"[{message.content_type}]"

    try:
        temp_message = await message.answer(text="⏳ Обрабатываю...")

        try:
            await save_message_to_owner(message)
        except Exception as e:
            logging.error(f"❌ Не удалось сохранить сообщение владельцу: {e}")

        message_counter[chat_id] += 1
        use_gpt = (message_counter[chat_id] >= PERSISTENT_THRESHOLD) or is_persistent(raw_text)

        if use_gpt:
            await asyncio.sleep(1.5)
            gpt_reply = await ask_gpt(chat_id, sender_name, text_for_gpt)
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=temp_message.message_id,
                text=gpt_reply,
                business_connection_id=message.business_connection_id
            )
            logging.info(f"🤖 Ответил {sender_name}")
        else:
            await asyncio.sleep(1)
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=temp_message.message_id,
                text=f"✅ {sender_name}, сообщение получено. Жди, отвечу.",
                business_connection_id=message.business_connection_id
            )
            logging.info(f"📨 Стандартный ответ для {sender_name}")

    except Exception as e:
        logging.error(f"❌ Ошибка при обработке сообщения: {e}")


@dp.message(F.chat.type == "private", ~F.business_connection_id)
async def test_direct_message(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Тестовый режим доступен только владельцу.")
        return
    text = message.text or ""
    if text.startswith("/start"):
        await message.answer(
            "🧪 Тестовый режим.\n\nНапиши любой текст — прогоню через нейросеть.\n"
            "⚠️ Основная логика работает, когда ДРУГОЙ человек пишет на ваш аккаунт."
        )
        return
    await message.answer("⏳ Думаю...")
    reply = await ask_gpt(message.chat.id, message.from_user.first_name or "Владелец", text)
    await message.answer(f"🤖 Ответ:\n\n{reply}")


async def main():
    logging.info("🚀 Запуск персонального бизнес-бота...")
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message", "edited_message",
            "business_connection", "business_message",
            "edited_business_message", "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
