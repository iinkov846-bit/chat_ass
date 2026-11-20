import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Подробное логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

# Проверка переменных при старте
if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не задан в переменных окружения!")
if not OWNER_ID:
    logging.error("❌ OWNER_ID не задан в переменных окружения!")
else:
    logging.info(f"✅ OWNER_ID получен: {OWNER_ID}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Команда /start для проверки работы
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"📩 Получен /start от {message.from_user.id} (@{message.from_user.username})")
    await message.answer("Бот работает! ✅")

# Обработчик всех остальных сообщений
@dp.message()
async def forward_to_owner(message: types.Message):
    logging.info(f"📩 Сообщение от {message.from_user.id} (@{message.from_user.username}): {message.text or '[медиа]'}")
    
    # Игнорируем сообщения от владельца
    if str(message.from_user.id) == str(OWNER_ID):
        logging.info("⏭ Сообщение от владельца, пропускаем")
        return
    
    try:
        await message.forward(int(OWNER_ID))
        logging.info(f"✅ Сообщение переслано владельцу")
    except Exception as e:
        logging.error(f"❌ Ошибка пересылки: {e}")
        await message.answer("Произошла ошибка при обработке сообщения.")

async def main():
    logging.info("🚀 Запуск бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
