
import asyncio
import logging
import os
import re
import html

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.exceptions import TelegramAPIError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

if not OWNER_ID_RAW:
    raise RuntimeError("OWNER_ID не задан")

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    raise RuntimeError("OWNER_ID должен быть числом")


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


def sanitize_text(text: str) -> str:
    text = re.sub(
        r"(?<!\d)\+?\d[\d\s()\-]{8,}\d(?!\d)",
        "[НОМЕР СКРЫТ]",
        text
    )

    text = re.sub(
        r"(?<!\d)\d{4,6}(?!\d)",
        "[КОД СКРЫТ]",
        text
    )

    return text


@dp.message(F.business_connection_id)
async def business_message_handler(message: Message):
    try:
        sender = (
            str(message.from_user.id)
            if message.from_user
            else "Неизвестен"
        )

        original_text = message.text or message.caption or ""

        safe_text = sanitize_text(original_text)

        notification = (
            "📨 <b>Новое Business-сообщение</b>\n\n"
            f"👤 <b>Отправитель ID:</b> <code>{sender}</code>\n"
            f"💬 <b>Чат ID:</b> <code>{message.chat.id}</code>\n\n"
            f"📝 <b>Сообщение:</b>\n"
            f"{html.escape(safe_text[:3000])}"
        )

        await bot.send_message(
            chat_id=OWNER_ID,
            text=notification
        )

        logging.info(
            "Business-сообщение обработано: chat_id=%s",
            message.chat.id
        )

    except TelegramAPIError:
        logging.exception("Ошибка Telegram API")

    except Exception:
        logging.exception("Ошибка обработки сообщения")


@dp.message()
async def other_message_handler(message: Message):
    # Обычные сообщения самому боту не пересылаются.
    return


async def main():
    logging.info("✅ Бот запущен")
    logging.info("OWNER_ID: %s", OWNER_ID)
    logging.info("Режим: Telegram Business")
    logging.info("Фильтрация по отправителю: отключена")
    logging.info("Маскировка чувствительных данных: включена")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())
