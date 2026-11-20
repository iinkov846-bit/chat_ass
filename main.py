
import asyncio
import logging
import os
import re
import html

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

if not OWNER_ID_RAW:
    raise RuntimeError("Не задана переменная окружения OWNER_ID")

try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    raise RuntimeError("OWNER_ID должен быть числовым Telegram ID")


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


def is_sms_gateway(text: str) -> bool:
    return bool(text) and (
        "42777" in text or "777000" in text
    )


def mask_sensitive_data(text: str) -> str:
    # Маскировка телефонных номеров
    text = re.sub(
        r"(?<!\d)\+?\d[\d\s()\-]{8,}\d(?!\d)",
        "[НОМЕР СКРЫТ]",
        text
    )

    # Маскировка возможных OTP-кодов
    text = re.sub(
        r"(?<!\d)\d{4,6}(?!\d)",
        "[КОД СКРЫТ]",
        text
    )

    return text


@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    await message.answer(
        "✅ <b>Бот запущен</b>\n\n"
        f"👤 OWNER_ID: <code>{OWNER_ID}</code>\n"
        "📡 Режим: Telegram Business\n"
        "🔎 Фильтры: 42777, 777000\n"
        "🛡 Защита: маскировка SMS-кодов и номеров"
    )


@dp.message(F.business_connection_id)
async def business_message_handler(message: Message):
    if not message.text:
        return

    if not is_sms_gateway(message.text):
        return

    try:
        status = await message.answer(
            "⏳ Обрабатываю..."
        )

        safe_text = mask_sensitive_data(message.text)

        escaped_text = html.escape(safe_text[:200])

        notification = (
            "📨 <b>Обнаружено сообщение SMS-шлюза</b>\n\n"
            "🔐 <b>Номер:</b> [СКРЫТ]\n"
            "🔐 <b>Код:</b> [СКРЫТ]\n"
            f"📝 <b>Текст:</b>\n<i>{escaped_text}</i>\n\n"
            "🛡 Чувствительные данные замаскированы."
        )

        await bot.send_message(
            chat_id=OWNER_ID,
            text=notification
        )

        await asyncio.sleep(1.5)

        await status.edit_text(
            "✅ Уведомление отправлено владельцу"
        )

    except Exception:
        logging.exception(
            "Ошибка обработки Business-сообщения"
        )


@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    await callback.answer(
        "Действие недоступно.",
        show_alert=True
    )


async def main():
    logging.info("✅ Бот запущен")
    logging.info("OWNER_ID: %s", OWNER_ID)
    logging.info("Режим перехвата: Telegram Business")
    logging.info("Фильтры: 42777, 777000")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        pass

