import os
import logging
import asyncio
import random
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (Railway → Variables) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")       # Токен от @BotFather
OWNER_ID_RAW = os.getenv("OWNER_ID")     # Ваш Telegram ID (куда слать копии)
DEBUG = os.getenv("DEBUG", "1") == "1"   # 1 = логировать сырые обновления, 0 = тишина

if not BOT_TOKEN or not OWNER_ID_RAW:
    raise ValueError("Ошибка: задай BOT_TOKEN и OWNER_ID в Railway!")
OWNER_ID = int(OWNER_ID_RAW)

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === НАСТРОЙКИ ПОВЕДЕНИЯ ===
# С какого сообщения подряд начинать грубить. Поставь 1, чтобы грубить с первого.
PERSISTENT_THRESHOLD = 2
TRIGGER_WORDS = {"ну", "алло", "ты тут", "ответь", "hello", "are you there", "ты здесь", "ау"}

message_counter = defaultdict(int)   # счётчик сообщений подряд от собеседника
last_phrase = {}                     # последняя фраза для антиповтора

# === 100 ГРУБЫХ ФРАЗ (редактируй freely) ===
RUDE_REPLIES = [
    "Чего надо? Я занят. Пиши по делу.",
    "Не долби, я всё видел. Отвечу, когда смогу.",
    "Ты серьёзно? Жди, не видишь — занят.",
    "Я тебе не справочная. Подожди.",
    "Хватит спамить. Освобожусь — напишу.",
    "Ещё одно 'ну' — и я вообще отвечать перестану.",
    "Сейчас не до тебя. Жди.",
    "Я занят. Твоё сообщение в очереди, не дёргайся.",
    "Тебе повторить? Я занят.",
    "Пиши по делу, а не спамь.",
    "Я не игнорю, я занят. Разницу чувствуешь?",
    "Подожди, не видишь — я не у телефона.",
    "Чего разнылся? Отвечу, когда освобожусь.",
    "Не надо паники. Я прочитаю и отвечу.",
    "Ты меня достал. Жди молча.",
    "Я занят, а не умер. Отвечу позже.",
    "Хватит дёргать. Всё дойдёт до меня.",
    "Не долби в личку. Я всё вижу.",
    "Твоё 'срочно' подождёт. Я занят.",
    "Я не обязан отвечать сию секунду. Жди.",
    "Спамить будешь в другом месте. Тут я занят.",
    "У меня дела. Твоё сообщение не горит.",
    "Прекрати долбить. Отвечу, когда смогу.",
    "Я занят. Не надо делать из этого драму.",
    "Ты читать умеешь? Я занят.",
    "Не видишь — я не у телефона. Подожди.",
    "Я тебе что, круглосуточная поддержка? Жди.",
    "Хватит. Я отвечу, когда освобожусь.",
    "Не дёргай меня. Всё прочитаю.",
    "Я занят. Твоё сообщение подождёт.",
    "Чего прилип? Я занят, отвечу позже.",
    "Не надо истерик. Я на связи, но занят.",
    "Ты меня задолбал. Жди.",
    "Я не игнорю специально. Я занят.",
    "Пиши нормально, а не 'ну' и 'ау'.",
    "Я занят. Не заставляй меня жалеть, что я на связи.",
    "Хватит ныть. Отвечу, когда смогу.",
    "Я занят, а не справочное бюро. Подожди.",
    "Твоё сообщение не срочнее моих дел. Жди.",
    "Не долби. Я и так отвечу, когда освобожусь.",
    "Я занят. Умерь пыл.",
    "Ты серьёзно думаешь, что я брошу всё ради тебя? Жди.",
    "Не надо давить. Я отвечу, когда смогу.",
    "Я занят. Твоя настойчивость не ускоряет ответ.",
    "Хватит стучаться. Я всё вижу.",
    "Я не у телефона. Прекрати долбить.",
    "Ты меня утомил. Жди.",
    "Я занят. Не надо делать вид, что это срочно.",
    "Пиши по делу. Пустой спам я игнорю.",
    "Я занят. Твоё 'ну' не поможет.",
    "Не дёргай. Отвечу, когда освобожусь.",
    "Я занят. Твоя паника — не моя проблема.",
    "Хватит. Я не обязан отвечать мгновенно.",
    "Я занят. Подожди, не будь навязчивым.",
    "Ты читать умеешь? Я сказал — позже.",
    "Я занят. Не надо превращать это в цирк.",
    "Не долби мне мозг. Жди.",
    "Я занят. Твоё сообщение в очереди.",
    "Прекрати спамить. Я отвечу, когда смогу.",
    "Я занят. Не надо истерить.",
    "Ты меня достал своим 'ну'. Жди.",
    "Я занят. Твоё 'срочно' подождёт.",
    "Не вижу смысла отвечать на спам. Пиши по делу.",
    "Я занят. Угомонись.",
    "Хватит дёргать меня по пустякам.",
    "Я занят. Твоё сообщение не пуп земли.",
    "Не надо давить на жалость. Я отвечу позже.",
    "Я занят. Твоя настойчивость раздражает.",
    "Пиши по делу, тогда отвечу быстрее.",
    "Я занят. Не долби, как в последний раз.",
    "Ты серьёзно? Я занят, отстань на время.",
    "Я занят. Не надо делать из себя жертву.",
    "Хватит. Я отвечу, когда освобожусь, и не раньше.",
    "Я занят. Твоё 'ау' не ускорит процесс.",
    "Не дёргай меня. Я и так всё вижу.",
    "Я занят. Твоё сообщение подождёт, и ты подождёшь.",
    "Прекрати долбить. Я не обязан реагировать мгновенно.",
    "Я занят. Не надо спамить, как будто я игнорю.",
    "Ты меня утомил своей настойчивостью. Жди.",
    "Я занят. Пиши по делу или жди.",
    "Хватит ныть. Я отвечу, когда смогу.",
    "Я занят. Твоё 'ну что' не поможет.",
    "Не долби. Я отвечу, когда освобожусь.",
    "Я занят. Твоя паника мне не указ.",
    "Ты читать умеешь? Я занят, отвечу позже.",
    "Я занят. Не надо превращать переписку в допрос.",
    "Хватит. Я не справочная, я занят.",
    "Я занят. Твоё сообщение не горит, угомонись.",
    "Не дёргай. Я отвечу, когда будет время.",
    "Я занят. Твоя настойчивость не делает тебя важнее.",
    "Пиши нормально. На 'ну' и 'ау' я не реагирую.",
    "Я занят. Не надо давить, это не работает.",
    "Хватит спамить. Я отвечу, когда освобожусь.",
    "Я занят. Твоё 'срочно' — не моя проблема.",
    "Не долби мне личку. Я всё вижу.",
    "Я занят. Твоё сообщение подождёт, не истери.",
    "Ты меня задолбал. Отвечу, когда смогу.",
    "Я занят. Не надо делать вид, что я обязан.",
    "Хватит. Я отвечу, когда освобожусь. Всё.",
    "Я занят. Пиши по делу, а не долби.",
]


def get_rude_reply(chat_id: int) -> str:
    """Случайная грубая фраза без повтора предыдущей для этого чата."""
    phrase = random.choice(RUDE_REPLIES)
    if len(RUDE_REPLIES) > 1:
        while phrase == last_phrase.get(chat_id):
            phrase = random.choice(RUDE_REPLIES)
    last_phrase[chat_id] = phrase
    return phrase


# === ОТЛАДКА (отключается переменной DEBUG=0) ===
@dp.update()
async def debug_all_updates(update: Update):
    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


def is_persistent(text: str) -> bool:
    if not text:
        return False
    return any(word in text.lower() for word in TRIGGER_WORDS)


# === СОХРАНЕНИЕ СООБЩЕНИЯ ВЛАДЕЛЬЦУ (независимая копия, не удалится) ===
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


# === Если владелец сам ответил — бот замолкает и сбрасывает счётчик ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    if getattr(message, "sender_business_bot", None) is not None:
        return
    chat_id = message.chat.id
    message_counter[chat_id] = 0
    last_phrase.pop(chat_id, None)
    logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — счётчик сброшен")


# === ОСНОВНОЙ ОБРАБОТЧИК: сообщения от других людей ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    raw_text = message.text or message.caption or ""

    try:
        # ШАГ 1: индикатор (business_connection_id подставляется автоматически)
        temp_message = await message.answer(text="⏳ Обрабатываю...")

        # ШАГ 2: сохраняем копию владельцу
        try:
            await save_message_to_owner(message)
        except Exception as e:
            logging.error(f"❌ Не удалось сохранить сообщение владельцу: {e}")

        # ШАГ 3: счётчик и решение — грубить или нейтрально
        message_counter[chat_id] += 1
        use_rude = (message_counter[chat_id] >= PERSISTENT_THRESHOLD) or is_persistent(raw_text)

        await asyncio.sleep(1)

        if use_rude:
            reply = get_rude_reply(chat_id)
            logging.info(f"😤 Грубый ответ для {sender_name}")
        else:
            reply = f"✅ {sender_name}, сообщение получено. Жди, отвечу."
            logging.info(f"📨 Нейтральный ответ для {sender_name}")

        # ШАГ 4: редактируем наше сообщение на финальный ответ
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=temp_message.message_id,
            text=reply,
            business_connection_id=message.business_connection_id
        )

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
            "🧪 Тестовый режим (без ИИ).\n\n"
            "Напиши любой текст — выдам случайную грубую фразу из списка.\n"
            "⚠️ Основная логика работает, когда ДРУГОЙ человек пишет на ваш аккаунт."
        )
        return
    await message.answer(get_rude_reply(message.chat.id))


async def main():
    logging.info("🚀 Запуск бота (без ИИ, 100 грубых фраз)...")
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
