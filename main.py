import os
import re
import html
import asyncio
import logging

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))  # твой Telegram user ID (число)
SESSION_NAME = os.getenv("SESSION_NAME", "userbot")

if not all([API_ID, API_HASH, OWNER_ID]):
    raise ValueError("Задай API_ID, API_HASH и OWNER_ID в Railway Variables!")

# === НАСТРОЙКИ ===
VZLOM_DELAY = 5

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

MIN_TROLL_DELAY = 3
MAX_TROLL_DELAY = 60
MAX_TROLL_MESSAGES = 20
TROLL_DELETE_AFTER = 5

# Активные задачи троллинга: chat_id -> asyncio.Task
troll_tasks: dict[int, asyncio.Task] = {}
delete_tasks: set[asyncio.Task] = set()

# Клиент Telethon
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


# ============================================================
# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
# ============================================================

async def schedule_delete(chat_id: int, message_id: int, delay: float):
    """Удаляет сообщение через delay секунд."""
    async def _delete():
        try:
            await asyncio.sleep(delay)
            await client.delete_messages(chat_id, [message_id])
            logging.info(f"🗑 Удалено сообщение {message_id}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.warning(f"⚠️ Не удалось удалить {message_id}: {e}")

    task = asyncio.create_task(_delete())
    delete_tasks.add(task)
    task.add_done_callback(delete_tasks.discard)


def parse_command(text: str | None):
    """Разбирает команду: возвращает (command, args) или (None, None)."""
    if not text or not text.startswith("/"):
        return None, None
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]  # убираем @botname
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


# ============================================================
# === ОБРАБОТЧИК ВСЕХ ВХОДЯЩИХ СООБЩЕНИЙ ===
# ============================================================

@client.on(events.NewMessage)
async def handler(event: events.NewMessage.Event):
    text = event.message.text or ""
    cmd, args = parse_command(text)

    if not cmd:
        return

    # === /взлом ЦЕЛЬ ===
    if cmd == "/взлом":
        target_raw = args.strip()
        if not target_raw:
            await event.respond("Использование:\n/взлом ХИТРЫЙ_ПАЦЫК")
            return

        target = html.escape(target_raw[:64])

        # Этап 1
        msg = await event.respond(
            f"🖥️ **ВЗЛОМ СИСТЕМЫ**\n\n"
            f"🎯 Цель: **{target}**\n"
            f"⏳ Начинаю взламывать...\n"
            f"🔌 Подключение к цели... `OK`\n"
            f"🔐 Обход защиты... `в процессе`"
        )

        await asyncio.sleep(VZLOM_DELAY)
        await msg.edit(
            f"✅ **Взлом удался, вывожу информацию...**\n\n"
            f"🎯 Цель: **{target}**\n"
            f"🔓 Доступ получен: `root@{target}`\n"
            f"📂 Чтение переписок... `67%`\n"
            f"🖼️ Выгрузка фото... `34%`\n"
            f"🔑 Подбор паролей... `готово`"
        )

        await asyncio.sleep(VZLOM_DELAY)
        await msg.edit(
            f"😂 **Ладно, это была шутка!**\n\n"
            f"🎯 **{target}** не взломан.\n"
            f"Никакого взлома не было, расслабься 🎭"
        )
        return

    # === /troll ===
    if cmd == "/troll":
        if event.sender_id != OWNER_ID:
            await event.respond("⛔ Команда /troll доступна только владельцу.")
            return

        chat_id = event.chat_id
        parts = args.split()

        # /troll stop
        if parts and parts[0].lower() == "stop":
            task = troll_tasks.get(chat_id)
            if task and not task.done():
                task.cancel()
                await event.respond("🛑 Троллинг остановлен. Уже отправленные сообщения удалятся сами.")
            else:
                await event.respond("Сейчас ничего не запущено.")
            return

        # /troll @username 5s
        if len(parts) < 2:
            await event.respond(
                "Использование:\n"
                "/troll @username 5s\n"
                "/troll stop"
            )
            return

        username = parts[0]
        delay_raw = parts[1].lower().rstrip("s")

        if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", username):
            await event.respond("❌ Укажи username в формате @username (5–32 символа).")
            return

        try:
            delay = float(delay_raw)
        except ValueError:
            await event.respond("❌ Задержка должна быть числом, например 5s.")
            return

        if delay < MIN_TROLL_DELAY or delay > MAX_TROLL_DELAY:
            await event.respond(f"❌ Задержка от {MIN_TROLL_DELAY}s до {MAX_TROLL_DELAY}s.")
            return

        if not TROLL_MESSAGES:
            await event.respond("❌ Список TROLL_MESSAGES пуст. Добавь фразы в main.py.")
            return

        existing = troll_tasks.get(chat_id)
        if existing and not existing.done():
            await event.respond("⚠️ В этом чате уже идёт троллинг. Останови: /troll stop")
            return

        # Старт
        status_msg = await event.respond(f"Троллинг {username} начался.")

        async def troll_worker():
            sent = 0
            try:
                while sent < MAX_TROLL_MESSAGES:
                    for phrase in TROLL_MESSAGES:
                        if sent >= MAX_TROLL_MESSAGES:
                            break
                        msg = await client.send_message(chat_id, f"{username}, {phrase}")
                        await schedule_delete(chat_id, msg.id, TROLL_DELETE_AFTER)
                        sent += 1
                        if sent < MAX_TROLL_MESSAGES:
                            await asyncio.sleep(delay)

                await client.send_message(chat_id, f"✅ Троллинг завершён. Отправлено: {sent}.")
            except asyncio.CancelledError:
                logging.info(f"🛑 Троллинг остановлен в чате {chat_id}")
                raise
            finally:
                troll_tasks.pop(chat_id, None)

        troll_tasks[chat_id] = asyncio.create_task(troll_worker())
        return


# ============================================================
# === ЗАПУСК ===
# ============================================================

async def main():
    logging.info("🚀 Запуск userbot'а...")
    await client.start()
    me = await client.get_me()
    logging.info(f"✅ Залогинен как: {me.first_name} (ID: {me.id})")
    logging.info(f"👑 Владелец: {OWNER_ID}")
    logging.info("Команды: /взлом, /troll (работают в ЛС, группах, каналах)")

    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
