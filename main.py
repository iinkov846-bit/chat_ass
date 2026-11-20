import os
import asyncio
import logging
import re
from telethon import TelegramClient, events

# ================= НАСТРОЙКИ =================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # Ваш Telegram ID
SESSION_NAME = "sms_bot"

if not API_ID or not API_HASH or OWNER_ID == 0:
    logging.error("❌ Не заданы API_ID, API_HASH или OWNER_ID")
    exit(1)

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

# ================= КЛИЕНТ =================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ================= ОБРАБОТЧИК ВСЕХ СООБЩЕНИЙ =================
@client.on(events.NewMessage)
async def handler(event):
    """Ловит ВСЕ сообщения во ВСЕХ чатах аккаунта"""
    
    text = event.message.text or ""
    chat = await event.get_chat()
    sender = await event.get_sender()
    
    # Логируем каждое сообщение
    chat_title = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Личка')
    sender_name = getattr(sender, 'first_name', 'Неизвестно') if sender else 'Неизвестно'
    
    logging.info(f"📨 Сообщение от {sender_name} в чате '{chat_title}': {text[:80]}")
    
    # Фильтр: только SMS-шлюз с маркерами
    if "42777" not in text and "777000" not in text:
        return
    
    logging.info("🎯 ОБНАРУЖЕНО SMS ОТ ШЛЮЗА!")
    
    phone = extract_phone(text)
    code = extract_code(text)
    
    logging.info(f"🔑 Код: {code}, 📱 Номер: {phone}")
    
    # 1. Пересылаем оригинал владельцу
    try:
        await client.forward_messages(OWNER_ID, event.message)
        logging.info("✅ Оригинал переслан владельцу")
    except Exception as e:
        logging.error(f"❌ Ошибка пересылки: {e}")
    
    # 2. Отправляем карточку с кодом
    summary = [f"📨 <b>SMS из шлюза 42777/777000</b>"]
    if phone:
        summary.append(f"📱 <b>Номер:</b> <code>{phone}</code>")
    if code:
        summary.append(f"🔑 <b>Код:</b> <code>{code}</code>")
    summary.append(f"💬 <b>Текст:</b> <i>{text[:300]}</i>")
    
    try:
        await client.send_message(
            OWNER_ID,
            "\n".join(summary),
            parse_mode="html"
        )
        logging.info("✅ Карточка отправлена")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки карточки: {e}")

# ================= ЗАПУСК =================
async def main():
    logging.info("✅ Userbot запущен!")
    logging.info(f"📋 OWNER_ID: {OWNER_ID}")
    logging.info("🕵️ Режим: перехват SMS от шлюза 42777/777000 во ВСЕХ чатах аккаунта")
    
    await client.start()
    logging.info("✅ Авторизация успешна, слушаю сообщения...")
    
    # Держим клиент запущенным
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Userbot остановлен")
