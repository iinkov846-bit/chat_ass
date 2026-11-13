import os
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

# DEBUG=1 — показывать сырые обновления Telegram
# DEBUG=0 — отключить подробные логи
DEBUG = os.getenv("DEBUG", "1") == "1"

if not BOT_TOKEN or not OWNER_ID_RAW:
    raise ValueError("Ошибка: задай BOT_TOKEN и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)


# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# === НАСТРОЙКИ ПОВЕДЕНИЯ ===

# С какого сообщения начинать грубые ответы.
# 2 = первое сообщение нейтральное, со второго — грубое.
# Если хочешь грубить сразу, поставь 1.
PERSISTENT_THRESHOLD = 2

TRIGGER_WORDS = {
    "ну",
    "алло",
    "ты тут",
    "ответь",
    "hello",
    "are you there",
    "ты здесь",
    "ау",
    "срочно",
    "быстрее",
}

message_counter = defaultdict(int)
last_phrase = {}


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


# === СЛУЖЕБНЫЕ ФУНКЦИИ ===

def get_rude_reply(chat_id: int) -> str:
    """
    Возвращает случайную грубую фразу.
    Не повторяет предыдущую фразу для этого же чата.
    """
    phrase = random.choice(RUDE_REPLIES)

    if len(RUDE_REPLIES) > 1:
        while phrase == last_phrase.get(chat_id):
            phrase = random.choice(RUDE_REPLIES)

    last_phrase[chat_id] = phrase
    return phrase


def is_persistent(text: str) -> bool:
    """Проверяет слова-маркеры настойчивости."""
    if not text:
        return False

    text_lower = text.lower()
    return any(word in text_lower for word in TRIGGER_WORDS)


def command_filter(name: str):
    """
    Надёжный фильтр для кириллических команд.
    Работает с:
    /взлом
    /взлом@username_bot
    /взлом аргументы
    """
    def checker(message: Message) -> bool:
        text = message.text or message.caption or ""

        if not text:
            return False

        first_word = text.split()[0].lower()
        command = first_word.split("@")[0]

        return command == f"/{name.lower()}"

    return checker


async def edit_message_safe(
    chat_id: int,
    message_id: int,
    text: str,
    business_connection_id: str | None = None,
):
    """
    Редактирует сообщение.
    Если это бизнес-чат — передаёт business_connection_id.
    Если это обычная личка бота — редактирует без него.
    """
    kwargs = {}

    if business_connection_id:
        kwargs["business_connection_id"] = business_connection_id

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        **kwargs
    )


async def run_prank(message: Message, steps: list[tuple[str, int | float]]):
    """
    Шуточная команда с редактированием сообщения.

    steps:
    [
        ("первый текст", 0),
        ("второй текст", 1),
        ("третий текст", 1),
    ]

    Первый текст отправляется сразу.
    Остальные тексты появляются через указанное количество секунд.
    """
    try:
        temp_message = await message.answer(steps[0][0])

        for text, delay in steps[1:]:
            await asyncio.sleep(delay)

            await edit_message_safe(
                chat_id=message.chat.id,
                message_id=temp_message.message_id,
                text=text,
                business_connection_id=message.business_connection_id
            )

    except Exception as e:
        logging.error(f"❌ Ошибка шуточной команды: {e}")


# === ОТЛАДКА ВСЕХ ОБНОВЛЕНИЙ ===
@dp.update()
async def debug_all_updates(update: Update):
    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


# === ПОДКЛЮЧЕНИЕ БОТА К TELEGRAM BUSINESS ===
@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(
        f"✅ Бот подключен к аккаунту: "
        f"{connection.user.first_name} "
        f"(ID подключения: {connection.id})"
    )


# ============================================================
# === ШУТОЧНЫЕ КОМАНДЫ ДЛЯ ВСЕХ ===
# ВАЖНО: эти обработчики должны быть выше основной логики,
# чтобы команды перехватывались первыми.
# ============================================================

@dp.business_message(command_filter("взлом"))
@dp.message(command_filter("взлом"))
async def cmd_vzlom(message: Message):
    await run_prank(message, [
        ("Начинаю взламывать...", 0),
        ("Взлом удался, вывожу информацию...", 1),
        ("Ладно наебал, это была шутка", 1),
    ])


@dp.business_message(command_filter("подзвонить"))
@dp.message(command_filter("подзвонить"))
async def cmd_podzvonit(message: Message):
    await run_prank(message, [
        ("Начинаю отправку 1000 SMS и 250 звонков.", 0),
        ('Отправка началась, напишите слово "БАНАН" для приостановления.', 2),
        ("Ебать, ты снова попался, ХАХА", 1),
    ])


# === СОХРАНЕНИЕ СООБЩЕНИЯ ВЛАДЕЛЬЦУ ===
async def save_message_to_owner(message: Message):
    """
    Делает независимую копию сообщения владельцу.
    Если отправитель удалит оригинал, копия у владельца останется.
    """
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "без username"

    header = (
        "📥 Новое сообщение вам\n"
        f"👤 От: {sender.full_name} ({username})\n"
        f"🆔 ID: {sender.id}\n"
        f"💬 Чат: {message.chat.id}"
    )

    if message.text:
        await bot.send_message(
            OWNER_ID,
            f"{header}\n\n💬 Текст:\n{message.text}"
        )
        return

    await bot.send_message(OWNER_ID, header)

    if message.photo:
        await bot.send_photo(
            OWNER_ID,
            message.photo[-1].file_id,
            caption=message.caption
        )

    elif message.video:
        await bot.send_video(
            OWNER_ID,
            message.video.file_id,
            caption=message.caption
        )

    elif message.voice:
        await bot.send_voice(
            OWNER_ID,
            message.voice.file_id,
            caption=message.caption
        )

    elif message.audio:
        await bot.send_audio(
            OWNER_ID,
            message.audio.file_id,
            caption=message.caption
        )

    elif message.document:
        await bot.send_document(
            OWNER_ID,
            message.document.file_id,
            caption=message.caption
        )

    elif message.animation:
        await bot.send_animation(
            OWNER_ID,
            message.animation.file_id,
            caption=message.caption
        )

    elif message.sticker:
        await bot.send_sticker(
            OWNER_ID,
            message.sticker.file_id
        )

    elif message.video_note:
        await bot.send_video_note(
            OWNER_ID,
            message.video_note.file_id
        )

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
        await bot.send_location(
            OWNER_ID,
            latitude=loc.latitude,
            longitude=loc.longitude
        )

    else:
        await bot.send_message(
            OWNER_ID,
            f"⚠️ Сообщение типа '{message.content_type}' "
            f"не удалось скопировать автоматически."
        )


# === ЕСЛИ ВЛАДЕЛЕЛЬ САМ ОТВЕТИЛ — СБРАСЫВАЕМ СЧЁТЧИК ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    # Игнорируем сообщения, которые отправил сам бот от имени владельца
    if getattr(message, "sender_business_bot", None) is not None:
        return

    chat_id = message.chat.id

    message_counter[chat_id] = 0
    last_phrase.pop(chat_id, None)

    logging.info(
        f"🔁 Владелец вступил в диалог с чатом {chat_id} — счётчик сброшен"
    )


# === ОСНОВНАЯ ЛОГИКА ДЛЯ ВХОДЯЩИХ СООБЩЕНИЙ ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    raw_text = message.text or message.caption or ""

    try:
        # 1. Отправляем временное сообщение
        temp_message = await message.answer("⏳ Обрабатываю...")

        # 2. Сохраняем копию владельцу
        try:
            await save_message_to_owner(message)
        except Exception as e:
            logging.error(f"❌ Не удалось сохранить сообщение владельцу: {e}")

        # 3. Увеличиваем счётчик сообщений
        message_counter[chat_id] += 1

        use_rude = (
            message_counter[chat_id] >= PERSISTENT_THRESHOLD
            or is_persistent(raw_text)
        )

        # 4. Пауза перед изменением сообщения
        await asyncio.sleep(1)

        if use_rude:
            reply = get_rude_reply(chat_id)
            logging.info(f"😤 Грубый ответ для {sender_name}")
        else:
            reply = f"✅ {sender_name}, сообщение получено. Жди, отвечу."
            logging.info(f"📨 Нейтральный ответ для {sender_name}")

        # 5. Редактируем временное сообщение
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
    """
    Обычные сообщения напрямую боту.
    Команды /взлом и /подзвонить обрабатываются выше и доступны всем.
    Здесь:
    - владелец может тестировать грубые фразы;
    - остальным показываем подсказку.
    """
    if message.from_user.id != OWNER_ID:
        await message.answer(
            "⛔ Обычный тестовый режим доступен только владельцу.\n\n"
            "Но шуточные команды доступны всем:\n"
            "/взлом\n"
            "/подзвонить"
        )
        return

    text = message.text or ""

    if text.startswith("/start"):
        await message.answer(
            "🧪 Тестовый режим.\n\n"
            "Напиши любой текст — выдам случайную грубую фразу.\n\n"
            "Команды:\n"
            "/взлом\n"
            "/подзвонить\n\n"
            "⚠️ Основная бизнес-логика работает, когда другой человек пишет на ваш аккаунт."
        )
        return

    await message.answer(get_rude_reply(message.chat.id))


# === ЗАПУСК ===
async def main():
    logging.info("🚀 Запуск бота без ИИ: 100 грубых фраз + шуточные команды")

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
