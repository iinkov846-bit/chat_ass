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
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "777000"))

if not BOT_TOKEN or OWNER_ID == 0:
    logging.error("❌ Ошибка: Не заданы переменные окружения BOT_TOKEN или OWNER_ID")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подробное логирование
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
    cleaned = re.sub(r'\+?\d{10,15}', '', text)
    match = re.search(r'\b(\d{4,6})\b', cleaned)
    return match.group(1) if match else None

# ================= УМНЫЙ ФИЛЬТР (С ЛОГАМИ) =================
def is_target_sms(message: types.Message) -> bool:
    """Проверяет, является ли сообщение целевым SMS от шлюза"""
    logging.info(f"🔍 Фильтр проверяет сообщение из чата {message.chat.id}")
    logging.info(f"🔍 Текст сообщения: {message.text[:100] if message.text else 'None'}")
    logging.info(f"🔍 TARGET_CHAT_ID = {TARGET_CHAT_ID}, OWNER_ID = {OWNER_ID}")
    
    # 1. Если это строго заданный ID чата (группа/канал)
    if message.chat.id == TARGET_CHAT_ID:
        logging.info("✅ Фильтр: сообщение из TARGET_CHAT_ID")
        return True
    
    # 2. Если это личка с владельцем, но текст содержит маркеры СМС-шлюза
    if message.chat.id == OWNER_ID and message.text:
        if "42777" in message.text or "777000" in message.text:
            logging.info("✅ Фильтр: личка с маркерами 42777/777000")
            return True
    
    logging.info("❌ Фильтр: сообщение НЕ прошло проверку")
    return False

# ================= КОМАНДЫ =================
@dp.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    logging.info(f"📍 Команда /get_id от {message.from_user.id} в чате {message.chat.id}")
    await message.answer(f"🆔 ID этого чата: `{message.chat.id}`\n👤 Ваш ID: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"📍 Команда /start от {message.from_user.id}")
    if message.from_user.id == OWNER_ID:
        await message.answer("🤖 Бот запущен. Ожидаю сообщения с маркерами '42777' или '777000'.")
    else:
        await message.answer("⛔ Доступ запрещён.")

# ================= ОСНОВНОЙ ОБРАБОТЧИК (С ЛОГАМИ) =================
@dp.message(is_target_sms)
async def handle_sms(message: types.Message):
    logging.info("🚀 ОБРАБОТЧИК SMS ЗАПУЩЕН!")
    logging.info(f"📩 Сообщение из чата: {message.chat.id}")
    logging.info(f"📩 Текст: {message.text}")
    logging.info(f"📩 OWNER_ID: {OWNER_ID}")
    
    # 1. Динамический статус в чате (если это не личка с самим собой)
    if message.chat.id != OWNER_ID:
        status_msg = await message.reply("⏳ Обрабатываю...")
        logging.info("⏳ Отправлен статус 'Обрабатываю...'")

    text = message.text or ""
    phone = extract_phone(text)
    code = extract_code(text)
    
    logging.info(f"🔑 Распознанный код: {code}")
    logging.info(f"📱 Распознанный номер: {phone}")

    # 2. Пересылаем оригинал владельцу
    try:
        logging.info(f"📤 Пытаюсь скопировать сообщение в чат {OWNER_ID}...")
        await message.copy_to(chat_id=OWNER_ID)
        logging.info("✅ Сообщение успешно скопировано владельцу!")
    except Exception as e:
        logging.error(f"❌ Ошибка копирования: {e}", exc_info=True)

    # 3. Формируем красивое уведомление
    summary_parts = ["📨 <b>Перехвачено SMS из шлюза:</b>"]
    summary_parts.append(f"📱 <b>Номер:</b> <code>{phone or 'не распознан'}</code>")
    summary_parts.append(f"🔑 <b>Код:</b> <code>{code or 'не распознан'}</code>")
    summary_parts.append(f"📝 <b>Исходный текст:</b> <i>{text[:100]}{'...' if len(text)>100 else ''}</i>")

    kb = None
    if code:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📋 Скопировать код {code}", callback_data=f"copy:{code}")]
        ])

    try:
        logging.info(f"📤 Отправляю карточку владельцу...")
        await bot.send_message(
            OWNER_ID,
            "\n".join(summary_parts),
            parse_mode="HTML",
            reply_markup=kb
        )
        logging.info("✅ Карточка успешно отправлена!")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки карточки: {e}", exc_info=True)

    # 4. Обновляем статус в чате (если это не личка)
    if message.chat.id != OWNER_ID:
        await asyncio.sleep(1.5)
        try:
            await status_msg.edit_text("✅ Сообщение переслано владельцу")
            logging.info("✅ Статус обновлен на 'Сообщение переслано владельцу'")
        except Exception as e:
            logging.error(f"❌ Ошибка обновления статуса: {e}")

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
    logging.info(f"📋 Настройки: OWNER_ID={OWNER_ID}, TARGET_CHAT_ID={TARGET_CHAT_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
