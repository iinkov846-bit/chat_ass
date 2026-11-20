import os
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ================= НАСТРОЙКИ (из переменных окружения Railway) =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0"))

# Проверка на наличие настроек при запуске
if not BOT_TOKEN or OWNER_ID == 0 or TARGET_CHAT_ID == 0:
    logging.error("❌ Ошибка: Не заданы переменные окружения BOT_TOKEN, OWNER_ID или TARGET_CHAT_ID")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка логирования для Railway (чтобы видеть ошибки в консоли)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ================= ПАРСЕРЫ =================
def extract_phone(text: str) -> str | None:
    if not text: return None
    # Ищем номер от 10 до 15 цифр (с возможным плюсом)
    match = re.search(r'(\+?\d{10,15})', text.replace(' ', '').replace('-', '').replace('(', '').replace(')', ''))
    return match.group(1) if match else None

def extract_code(text: str) -> str | None:
    if not text: return None
    # Убираем номера, чтобы не перепутать их с кодом
    cleaned = re.sub(r'\+?\d{10,15}', '', text)
    match = re.search(r'\b(\d{4,6})\b', cleaned)
    return match.group(1) if match else None

# ================= КОМАНДЫ =================
@dp.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    await message.answer(f"🆔 ID этого чата: `{message.chat.id}`", parse_mode="Markdown")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer("🤖 Бот запущен на Railway. Перехватываю коды и номера.")
    else:
        await message.answer("⛔ Доступ запрещён.")

# ================= ОСНОВНОЙ ОБРАБОТЧИК =================
@dp.message(F.chat.id == TARGET_CHAT_ID)
async def handle_sms(message: types.Message):
    # 1. Динамический статус в чате
    status_msg = await message.reply("⏳ Обрабатываю...")

    text = message.text or ""
    phone = extract_phone(text)
    code = extract_code(text)

    # 2. Пересылаем оригинал владельцу (копия не удалится)
    try:
        await message.copy_to(chat_id=OWNER_ID)
    except Exception as e:
        logging.error(f"Ошибка копирования: {e}")

    # 3. Формируем красивое уведомление
    summary_parts = ["📨 <b>Перехвачено SMS:</b>"]
    summary_parts.append(f"📱 <b>Номер:</b> <code>{phone or 'не распознан'}</code>")
    summary_parts.append(f"🔑 <b>Код:</b> <code>{code or 'не распознан'}</code>")

    kb = None
    if code:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📋 Скопировать код {code}", callback_data=f"copy:{code}")]
        ])

    await bot.send_message(
        OWNER_ID,
        "\n".join(summary_parts),
        parse_mode="HTML",
        reply_markup=kb
    )

    # 4. Обновляем статус в чате
    await asyncio.sleep(1.5)
    try:
        await status_msg.edit_text("✅ Сообщение переслано владельцу")
    except Exception:
        pass # Игнорируем ошибки, если сообщение уже удалили или изменили

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
    logging.info("✅ Бот успешно запущен и начал работу!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
