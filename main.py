import os
import json
import logging
import asyncio
import random
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update


# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")
DEBUG = os.getenv("DEBUG", "1") == "1"

# Необязательно: можно вручную задать ID бизнес-подключения,
# чтобы био менялось сразу после деплоя, даже без входящих сообщений.
BUSINESS_CONNECTION_ID = os.getenv("BUSINESS_CONNECTION_ID")

if not BOT_TOKEN or not OWNER_ID_RAW:
    raise ValueError("Ошибка: задай BOT_TOKEN и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)


# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# === НАСТРОЙКИ ПОВЕДЕНИЯ ===
PERSISTENT_THRESHOLD = 2
TRIGGER_WORDS = {
    "ну", "алло", "ты тут", "ответь", "hello",
    "are you there", "ты здесь", "ау", "срочно", "быстрее",
}

message_counter = defaultdict(int)
last_phrase = {}


# === РОТАЦИЯ БИО (строка "О себе" в профиле) ===
BIO_TEXTS = [
    "О нет, снова этот бот отвечает...",
    "Когда уже вернётся владелец этого балбеса",
    "Он чё, пьяный?",
    "Походу Админ споил бота",
    "Надеюсь мои ответы не слишком грубые...",
    "Админ походу снова пошёл курить зелень",
]

BIO_INTERVAL_SECONDS = 2 * 60 * 60  # каждые 2 часа
STATE_FILE = "business_state.json"
bio_index = 0


# === 100 ГРУБЫХ ФРАЗ ===
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

    "Я занят. Хватит выпрашивать ответ.",
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


# === УМНЫЕ ОТВЕТЫ ===
GREETINGS = {"привет", "прив", "приветик", "здравствуй", "здравствуйте", "хай", "ку"}
QUESTIONS = {"что делаешь", "чем занимаешься", "как дела", "как ты", "чем занят", "что поделываешь"}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace())
    return " ".join(cleaned.split())


def get_smart_reply(text: str) -> str | None:
    normalized = normalize_text(text)
    if normalized in GREETINGS:
        return "Привет, как ты?"
    if normalized in QUESTIONS:
        return "Строю небоскрёб из бананов"
    return None


def get_rude_reply(chat_id: int) -> str:
    phrase = random.choice(RUDE_REPLIES)
    if len(RUDE_REPLIES) > 1:
        while phrase == last_phrase.get(chat_id):
            phrase = random.choice(RUDE_REPLIES)
    last_phrase[chat_id] = phrase
    return phrase


def is_persistent(text: str) -> bool:
    if not text:
        return False
    return any(word in text.lower() for word in TRIGGER_WORDS)


def command_filter(*names: str):
    lowered = {f"/{n.lower()}" for n in names}

    def checker(message: Message) -> bool:
        text = message.text or message.caption or ""
        if not text:
            return False
        first = text.split()[0].lower().split("@")[0]
        return first in lowered

    return checker


async def edit_message_safe(chat_id, message_id, text, business_connection_id=None):
    kwargs = {}
    if business_connection_id:
        kwargs["business_connection_id"] = business_connection_id
    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)


async def run_prank(message: Message, steps):
    try:
        temp = await message.answer(steps[0][0], parse_mode="HTML")
        for text, delay in steps[1:]:
            await asyncio.sleep(delay)
            kwargs = {}
            if message.business_connection_id:
                kwargs["business_connection_id"] = message.business_connection_id
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=temp.message_id,
                text=text,
                parse_mode="HTML",
                **kwargs
            )
    except Exception as e:
        logging.error(f"❌ Ошибка шуточной команды: {e}")


# ============================================================
# === БИО: хранение ID подключения и смена строки "О себе" ===
# ============================================================

def load_business_id():
    global BUSINESS_CONNECTION_ID
    if BUSINESS_CONNECTION_ID:
        return
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                BUSINESS_CONNECTION_ID = data.get("business_connection_id")
                logging.info(f"💾 Загружен business_connection_id: {BUSINESS_CONNECTION_ID}")
    except Exception as e:
        logging.error(f"❌ Не удалось загрузить состояние: {e}")


def save_business_id(cid: str):
    global BUSINESS_CONNECTION_ID
    if not cid or cid == BUSINESS_CONNECTION_ID:
        return
    BUSINESS_CONNECTION_ID = cid
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"business_connection_id": cid}, f, ensure_ascii=False)
        logging.info(f"💾 Сохранён business_connection_id: {cid}")
    except Exception as e:
        logging.error(f"❌ Не удалось сохранить состояние: {e}")


async def update_bio() -> tuple[bool, str]:
    """Меняет строку 'О себе' на следующую фразу из списка."""
    global bio_index

    if not BUSINESS_CONNECTION_ID:
        msg = "Нет ID бизнес-подключения. Пусть кто-нибудь напишет вам или переподключите бота."
        logging.warning(msg)
        return False, msg

    if not hasattr(bot, "set_business_account_bio"):
        msg = "aiogram слишком старый — обнови requirements.txt (aiogram>=3.7.0)."
        logging.error(msg)
        return False, msg

    text = BIO_TEXTS[bio_index % len(BIO_TEXTS)]
    bio_index += 1

    try:
        await bot.set_business_account_bio(
            business_connection_id=BUSINESS_CONNECTION_ID,
            bio=text
        )
        logging.info(f"✅ Био обновлено: {text}")
        return True, text
    except Exception as e:
        msg = f"{e}"
        logging.error(f"❌ Не удалось обновить био: {msg}")
        return False, msg


async def bio_rotator():
    """Фоновая задача: меняет био каждые 2 часа."""
    while True:
        await asyncio.sleep(BIO_INTERVAL_SECONDS)
        await update_bio()


# === перехват обновлений: логи + запоминание ID подключения ===
@dp.update()
async def on_update(update: Update):
    cid = None
    if update.business_connection:
        cid = update.business_connection.id
    elif update.business_message and update.business_message.business_connection_id:
        cid = update.business_message.business_connection_id
    elif update.edited_business_message and update.edited_business_message.business_connection_id:
        cid = update.edited_business_message.business_connection_id

    if cid:
        save_business_id(cid)

    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


# ============================================================
# === КОМАНДЫ (регистрируются ДО основной логики) ===
# ============================================================

@dp.business_message(command_filter("команды", "commands", "help"))
@dp.message(command_filter("команды", "commands", "help"))
async def cmd_commands(message: Message):
    text = (
        "📋 <b>Список команд</b>\n\n"
        "🎭 <b>Для всех:</b>\n"
        "/команды — показать это меню\n"
        "/взлом — шуточный «взлом» с красивыми этапами\n"
        "/подзвонить — шуточная «отправка 1000 SMS и 250 звонков»\n\n"
        "👑 <b>Только владелец:</b>\n"
        "/refesh — принудительно сменить строку «О себе» в профиле (не ждать 2 часа)\n\n"
        "ℹ️ Бот также отвечает на приветствия и вопросы, "
        "а настойчивым собеседникам выдаёт грубые фразы."
    )
    await message.answer(text, parse_mode="HTML")


@dp.business_message(command_filter("взлом"))
@dp.message(command_filter("взлом"))
async def cmd_vzlom(message: Message):
    await run_prank(message, [
        (
            "🖥️ <b>ВЗЛОМ СИСТЕМЫ</b>\n\n"
            "⏳ Начинаю взламывать...\n"
            "🔌 Подключение к цели... <code>OK</code>\n"
            "🔐 Обход защиты... <code>в процессе</code>",
            0
        ),
        (
            "✅ <b>Взлом удался, вывожу информацию...</b>\n\n"
            "🔓 Доступ получен: <code>root@target</code>\n"
            "📂 Чтение переписок... <code>67%</code>\n"
            "🖼️ Выгрузка фото... <code>34%</code>\n"
            "🔑 Подбор паролей... <code>готово</code>",
            4
        ),
        (
            "😂 <b>Ладно, наебал — это была шутка!</b>\n\n"
            "Никакого взлома не было, расслабься.\n"
            "Ты просто попался на пранк 🎭",
            4
        ),
    ])


@dp.business_message(command_filter("подзвонить"))
@dp.message(command_filter("подзвонить"))
async def cmd_podzvonit(message: Message):
    await run_prank(message, [
        (
            "📱 <b>МАССОВАЯ ОТПРАВКА</b>\n\n"
            "⏳ Начинаю отправку <b>1000 SMS</b> и <b>250 звонков</b>.\n"
            "📡 Подключение к шлюзу... <code>OK</code>\n"
            "📋 Формирование очереди... <code>1250/1250</code>",
            0
        ),
        (
            "🚀 <b>Отправка началась!</b>\n\n"
            "📨 SMS отправлено: <code>237/1000</code>\n"
            "📞 Звонков сделано: <code>58/250</code>\n\n"
            "Напиши слово <b>«БАНАН»</b> для приостановления.",
            4
        ),
        (
            "😂 <b>Ебать, ты снова попался, ХАХА!</b>\n\n"
            "Никаких SMS и звонков не было 🎭\n"
            "Это просто шутка, расслабься 😄",
            4
        ),
    ])


@dp.business_message(command_filter("refesh", "refresh"))
@dp.message(command_filter("refesh", "refresh"))
async def cmd_refesh(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Команда /refesh доступна только владельцу аккаунта.")
        return

    ok, info = await update_bio()
    if ok:
        await message.answer(f"✅ Био обновлено:\n{info}")
    else:
        await message.answer(
            "❌ Не удалось обновить био.\n\n"
            f"{info}\n\n"
            "Проверь, что бот подключён в Telegram Business и имеет право менять био/профиль."
        )


# === СОХРАНЕНИЕ СООБЩЕНИЯ ВЛАДЕЛЬЦУ ===
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


# === владелец сам ответил — сбрасываем счётчик ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    if getattr(message, "sender_business_bot", None) is not None:
        return
    chat_id = message.chat.id
    message_counter[chat_id] = 0
    last_phrase.pop(chat_id, None)
    logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — счётчик сброшен")


# === ОСНОВНАЯ ЛОГИКА ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    raw_text = message.text or message.caption or ""

    try:
        temp_message = await message.answer("⏳ Обрабатываю...")

        try:
            await save_message_to_owner(message)
        except Exception as e:
            logging.error(f"❌ Не удалось сохранить сообщение владельцу: {e}")

        message_counter[chat_id] += 1
        smart_reply = get_smart_reply(raw_text)
        use_rude = (
            message_counter[chat_id] >= PERSISTENT_THRESHOLD
            or is_persistent(raw_text)
        )

        await asyncio.sleep(1)

        if smart_reply:
            reply = smart_reply
            logging.info(f"💬 Умный ответ для {sender_name}")
        elif use_rude:
            reply = get_rude_reply(chat_id)
            logging.info(f"😤 Грубый ответ для {sender_name}")
        else:
            reply = f"✅ {sender_name}, сообщение получено. Жди, отвечу."
            logging.info(f"📨 Нейтральный ответ для {sender_name}")

        await edit_message_safe(
            chat_id=message.chat.id,
            message_id=temp_message.message_id,
            text=reply,
            business_connection_id=message.business_connection_id
        )

    except Exception as e:
        logging.error(f"❌ Ошибка при обработке сообщения: {e}")


# === ЛИЧКА БОТА ===
@dp.message(F.chat.type == "private", ~F.business_connection_id)
async def handle_direct_message(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer(
            "⛔ Обычный тестовый режим доступен только владельцу.\n\n"
            "Но команды доступны всем:\n"
            "/команды\n"
            "/взлом\n"
            "/подзвонить"
        )
        return

    text = message.text or ""

    if text.startswith("/start"):
        await message.answer(
            "🧪 Тестовый режим.\n\n"
            "Напиши текст — выдам умный ответ или случайную грубую фразу.\n\n"
            "Команды:\n"
            "/команды\n"
            "/взлом\n"
            "/подзвонить\n"
            "/refesh — сменить био профиля"
        )
        return

    smart = get_smart_reply(text)
    if smart:
        await message.answer(smart)
    else:
        await message.answer(get_rude_reply(message.chat.id))


# === ЗАПУСК ===
async def main():
    logging.info("🚀 Запуск бота: 100 фраз, команды, ротация био каждые 2 часа")

    load_business_id()

    # Сразу ставим первое био, если ID уже известен
    if BUSINESS_CONNECTION_ID:
        await update_bio()

    # Фоновая ротация био
    asyncio.create_task(bio_rotator())

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
