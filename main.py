import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токен и ID владельца из переменных окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик всех входящих сообщений
@dp.message()
async def forward_to_owner(message: types.Message):
    # Игнорируем сообщения от самого владельца, чтобы избежать бесконечного цикла
    if message.from_user.id == OWNER_ID:
        return
    
    try:
        # Пересылаем сообщение владельцу
        await message.forward(OWNER_ID)
    except Exception as e:
        logging.error(f"Не удалось переслать сообщение: {e}")

async def main():
    logging.info("Бот успешно запущен!")
    # Запускаем поллинг (опрос серверов Telegram)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
