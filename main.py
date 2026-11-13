import os
import re
import html
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not BOT_TOKEN or not OWNER_ID_RAW:
    raise ValueError("Задай BOT_TOKEN и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# === НАСТРОЙКИ ===
# ============================================================

VZLOM_DELAY = 5          # пауза между этапами /взлом

# === СООБЩЕНИЯ ДЛЯ /troll (добавь свои фразы сюда) ===
# Бот сам подставит "@username, " в начало каждой строки.
TROLL_MESSAGES = [
    "я те мать ебал, ха",
    "ты же жирная свинья нахуй",
    "фу ебать ты свинобаза сука.",
    "я те ебало своим хуем рвал",
    "у тя мать на столько толстая что трощит мою сперму своим весом",
    "я тебе всю семью ебал долбоеб",
    "ты же свинорылий сынок шлюхи ебать",
    "ты же шаболда ебанная",
    "нахуй ты мой хуй посасывала свинья ебанная?",
    "ебанись об столб либо я сейчас тебе ебало залью",
    "ты снова моей спермой объебалась шаболда",
    "ну ты внатуре хуесос ебанный, вякни мне в хуй чо нить",
    "как я те семью ебал расскажи",
    "ты жертва инцеста нахуй.",
    "у тебя мать на столько толстая что земля приостанавливается каждый раз когда она встаёт с кровати",
    "ты же дочь бляди нахуй",
    "почему ты такое тупое животное нахуй?",
    "слыш я же те внатуре матуху ебал в париже",
    "ты рил сосал хуй у моего бати за кусок банана?",
    "поч твоя шлюха матерь отдаётся мне за сперму?",
    "смешно наблюдать как твоя мать мучается когда я ей не даю пососать свой член",
    "смотри, ебать ты даун ты снова отлавливаешь харчки в своё ебало",
    "я снова те матуху выебал, уже подзаебался",
]

MIN_TROLL_DELAY = 3      # минимальная задержка между сообщениями
MAX_TROLL_DELAY = 60     # максимальная задержка
MAX_TROLL_MESSAGES = 20  # максимум сообщений за запуск

TROLL_DELETE_AFTER = 5   # через сколько секунд удалять сообщения троллинга

troll_tasks: dict[int, asyncio.Task] = {}
delete_tasks: set[asyncio.Task] = set()   # задачи автоудаления


# ============================================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
# ============================================================

def command_filter(*names: str):
    lowered = {f"/{n.lower()}" for n in names}

    def checker(message: Message) -> bool:
        text = message.text or message.caption or ""
        if not text:
            return False
        first = text.split()[0].lower().split("@")[0]
        return first in lowered

    return checker


async def send_text(chat_id, text, business_connection_id=None, parse_mode=None) -> Message:
    """Отправляет сообщение и возвращает его (чтобы знать message_id для удаления)."""
    kwargs = {}
    if business_connection_id:
        kwargs["business_connection_id"] = business_connection_id
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    return await bot.send_message(chat_id=chat_id, text=text, **kwargs)


async def edit_text(chat_id, message_id, text, business_connection_id=None, parse_mode=None):
    kwargs = {}
    if business_connection_id:
        kwargs["business_connection_id"] = business_connection_id
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)


async def delete_later(chat_id: int, message_id: int, business_connection_id: str | None, delay: float):
    """Удаляет сообщение через заданное количество секунд."""
    try:
        await asyncio.sleep(delay)

        if business_connection_id:
            # Удаление от имени бизнес-аккаунта
            if hasattr(bot, "delete_business_messages"):
                await bot.delete_business_messages(
                    business_connection_id=business_connection_id,
                    chat_id=chat_id,
                    message_ids=[message_id]
                )
            else:
                logging.warning("Обнови aiogram — нет метода delete_business_messages")
        else:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)

        logging.info(f"🗑 Удалено сообщение {message_id}")

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logging.warning(f"⚠️ Не удалось удалить сообщение {message_id}: {e}")


def schedule_delete(chat_id: int, message_id: int, business_connection_id: str | None):
    """Запускает автоудаление в фоне, не блокируя отправку следующих сообщений."""
    task = asyncio.create_task(
        delete_later(chat_id, message_id, business_connection_id, TROLL_DELETE_AFTER)
    )
    delete_tasks.add(task)
    task.add_done_callback(delete_tasks.discard)


# ============================================================
# === КОМАНДА /взлом ЦЕЛЬ ===
# ============================================================

@dp.business_message(command_filter("взлом"))
@dp.message(command_filter("взлом"))
async def cmd_vzlom(message: Message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование:\n/взлом ХИТРЫЙ_ПАЦЫК")
        return

    target = html.escape(parts[1].strip()[:64])
    cid = message.business_connection_id

    temp = await message.answer(
        f"🖥️ <b>ВЗЛОМ СИСТЕМЫ</b>\n\n"
        f"🎯 Цель: <b>{target}</b>\n"
        f"⏳ Начинаю взламывать...\n"
        f"🔌 Подключение к цели... <code>OK</code>\n"
        f"🔐 Обход защиты... <code>в процессе</code>",
        parse_mode="HTML"
    )

    await asyncio.sleep(VZLOM_DELAY)
    await edit_text(
        message.chat.id, temp.message_id,
        f"✅ <b>Взлом удался, вывожу информацию...</b>\n\n"
        f"🎯 Цель: <b>{target}</b>\n"
        f"🔓 Доступ получен: <code>root@{target}</code>\n"
        f"📂 Чтение переписок... <code>67%</code>\n"
        f"🖼️ Выгрузка фото... <code>34%</code>\n"
        f"🔑 Подбор паролей... <code>готово</code>",
        business_connection_id=cid, parse_mode="HTML"
    )

    await asyncio.sleep(VZLOM_DELAY)
    await edit_text(
        message.chat.id, temp.message_id,
        f"😂 <b>Ладно, это была шутка!</b>\n\n"
        f"🎯 <b>{target}</b> не взломан.\n"
        f"Никакого взлома не было, расслабься 🎭",
        business_connection_id=cid, parse_mode="HTML"
    )


# ============================================================
# === ТРОЛЛИНГ ===
# ============================================================

async def troll_worker(chat_id: int, username: str, delay: float, business_connection_id: str | None):
    sent = 0
    try:
        while sent < MAX_TROLL_MESSAGES:
            for phrase in TROLL_MESSAGES:
                if sent >= MAX_TROLL_MESSAGES:
                    break

                msg = await send_text(chat_id, f"{username}, {phrase}", business_connection_id)
                schedule_delete(chat_id, msg.message_id, business_connection_id)

                sent += 1
                if sent < MAX_TROLL_MESSAGES:
                    await asyncio.sleep(delay)

        await send_text(
            chat_id,
            f"✅ Троллинг завершён. Отправлено сообщений: {sent}.",
            business_connection_id
        )

    except asyncio.CancelledError:
        logging.info(f"🛑 Троллинг остановлен в чате {chat_id}")
        raise
    finally:
        troll_tasks.pop(chat_id, None)


@dp.business_message(command_filter("troll"))
@dp.message(command_filter("troll"))
async def cmd_troll(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Команда /troll доступна только владельцу.")
        return

    chat_id = message.chat.id
    cid = message.business_connection_id
    parts = (message.text or "").split()

    # /troll stop
    if len(parts) >= 2 and parts[1].lower() == "stop":
        task = troll_tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
            await message.answer("🛑 Троллинг остановлен. Уже отправленные сообщения удалятся сами.")
        else:
            await message.answer("Сейчас ничего не запущено.")
        return

    # /troll @username 5s
    if len(parts) < 3:
        await message.answer(
            "Использование:\n"
            "/troll @username 5s\n"
            "/troll stop"
        )
        return

    username = parts[1]
    delay_raw = parts[2].lower().rstrip("s")

    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", username):
        await message.answer("❌ Укажи username в формате @username (5–32 символа: буквы, цифры, _).")
        return

    try:
        delay = float(delay_raw)
    except ValueError:
        await message.answer("❌ Задержка должна быть числом, например 5s.")
        return

    if delay < MIN_TROLL_DELAY or delay > MAX_TROLL_DELAY:
        await message.answer(f"❌ Задержка должна быть от {MIN_TROLL_DELAY}s до {MAX_TROLL_DELAY}s.")
        return

    if not TROLL_MESSAGES:
        await message.answer("❌ Список TROLL_MESSAGES пуст. Добавь фразы в main.py.")
        return

    existing = troll_tasks.get(chat_id)
    if existing and not existing.done():
        await message.answer("⚠️ В этом чате уже идёт троллинг. Останови: /troll stop")
        return

    temp = await message.answer("⏳ Подготовка троллинга...")
    await edit_text(chat_id, temp.message_id, f"Троллинг {username} начался.", business_connection_id=cid)

    troll_tasks[chat_id] = asyncio.create_task(
        troll_worker(chat_id, username, delay, cid)
    )


async def main():
    logging.info("🚀 Бот запущен. Команды: /взлом, /troll")
    await dp.start_polling(bot, allowed_updates=["message", "business_message"])


if __name__ == "__main__":
    asyncio.run(main())
