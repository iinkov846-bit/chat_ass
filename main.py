import os
import logging
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update
from openai import AsyncOpenAI

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (задаются в Railway → Variables) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")           # Токен от @BotFather
OWNER_ID = int(os.getenv("OWNER_ID"))        # Ваш Telegram ID (куда слать копии)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Ключ OpenAI (sk-...)

if not all([BOT_TOKEN, OWNER_ID, OPENAI_API_KEY]):
    raise ValueError("Ошибка: Не все переменные окружения заданы в Railway!")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# === НАСТРОЙКИ ПОВЕДЕНИЯ ===
PERSISTENT_THRESHOLD = 2        # С какого сообщения подряд включать GPT
CONTEXT_HISTORY_SIZE = 10       # Сколько сообщений помнить для контекста GPT
TRIGGER_WORDS = {"ну", "алло", "ты тут", "ответь", "hello", "are you there", "ты здесь", "ау"}

# === ХРАНИЛИЩА В ПАМЯТИ (ключ = chat_id собеседника) ===
message_counter = defaultdict(int)    # Счётчик сообщений подряд
chat_history = defaultdict(list)      # История для GPT

# === "ДУША" АССИСТЕНТА ===
SYSTEM_PROMPT = """Ты — личный ассистент владельца этого Telegram-аккаунта. 
Отвечай от первого лица ("я"), как будто ты — это он сам.
Стиль: дружелюбный, краткий, естественный, как в обычной переписке.
НИКОГДА не упоминай, что ты ИИ, языковая модель или бот.
Если спрашивают, кто ты — отвечай уклончиво: "Просто занят сейчас, отвечу позже".
Если собеседник настойчив — вежливо пообещай ответить в течение дня."""


# === ОТЛАДКА: логируем все входящие обновления (можно удалить после отладки) ===
@dp.update()
async def debug_all_updates(update: Update):
    logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


# === Подключение бота к бизнес-аккаунту ===
@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


# === Проверка на "настойчивость" ===
def is_persistent(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(word in text_lower for word in TRIGGER_WORDS)


# === Запрос к ChatGPT с учётом истории ===
async def ask_gpt(chat_id: int, user_name: str, new_message: str) -> str:
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


# === НАДЁЖНОЕ СОХРАНЕНИЕ СООБЩЕНИЯ ВЛАДЕЛЬЦУ ===
# Не используем copy_message, т.к. он не поддерживает business_connection_id.
# Вместо этого отправляем владельцу независимую копию内容的 сообщения.
async def save_message_to_owner(message: Message):
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "без username"
    header = (
        "📥 Новое сообщение вам\n"
        f"👤 От: {sender.full_name} ({username})\n"
        f"🆔 ID: {sender.id}\n"
        f"💬 Чат: {message.chat.id}"
    )

    # Текст: сохраняем одной消息ью с заголовком
    if message.text:
        await bot.send_message(
            chat_id=OWNER_ID,
            text=f"{header}\n\n💬 Текст:\n{message.text}"
        )
        return

    # Для медиа сначала отправляем заголовок, потом сам файл
    await bot.send_message(chat_id=OWNER_ID, text=header)

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
        await bot.send_contact(
            OWNER_ID,
            phone_number=c.phone_number,
            first_name=c.first_name,
            last_name=c.last_name
        )
    elif message.location:
        loc = message.location
        await bot.send_location(OWNER_ID, latitude=loc.latitude, longitude=loc.longitude)
    else:
        await bot.send_message(
            OWNER_ID,
            f"⚠️ Получено сообщение типа '{message.content_type}', "
            f"его не удалось скопировать автоматически."
        )


# === Сообщения ОТ ВЛАДЕЛЬЦА: сбрасываем счётчик (бот замолкает) ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    # Игнорируем сообщения, отправленные самим ботом от имени владельца
    if getattr(message, "sender_business_bot", None) is not None:
        return
    chat_id = message.chat.id
    if chat_id in message_counter:
        message_counter[chat_id] = 0
        chat_history[chat_id].clear()
        logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — бот замолкает")


# === ОСНОВНОЙ ОБРАБОТЧИК: сообщения от других людей ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    raw_text = message.text or message.caption or ""
    text_for_gpt = raw_text or f"[{message.content_type}]"

    try:
        # ШАГ 1: индикатор (business_connection_id подставляется АВТОМАТИЧЕСКИ)
        temp_message = await message.answer(text="⏳ Обрабатываю...")

        # ШАГ 2: сохраняем копию владельцу (защита от удаления)
        try:
            await save_message_to_owner(message)
        except Exception as e:
            logging.error(f"❌ Не удалось сохранить сообщение владельцу: {e}")

        # ШАГ 3: счётчик и решение, нужен ли GPT
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
            logging.info(f"🤖 GPT ответил {sender_name}")
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


# === ТЕСТОВЫЙ РЕЖИМ: пишите боту напрямую (только для владельца) ===
@dp.message(F.chat.type == "private", ~F.business_connection_id)
async def test_direct_message(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Тестовый режим доступен только владельцу.")
        return
    text = message.text or ""
    if text.startswith("/start"):
        await message.answer(
            "🧪 Тестовый режим активен!\n\n"
            "Напишите любой текст — я прогоню его через GPT.\n\n"
            "⚠️ Основная логика работает, когда ДРУГОЙ человек пишет на ваш аккаунт."
        )
        return
    await message.answer("⏳ Обрабатываю через GPT...")
    reply = await ask_gpt(message.chat.id, message.from_user.first_name or "Владелец", text)
    await message.answer(f"🤖 Ответ GPT:\n\n{reply}")


# === ЗАПУСК ===
async def main():
    logging.info("🚀 Запуск персонального бизнес-бота...")
    # Явно запрашиваем бизнес-обновления, иначе Telegram их не присылает
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "edited_message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
