import os
import json
import logging
import asyncio
from datetime import datetime
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BusinessConnection, Update
from openai import AsyncOpenAI

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OWNER_ID_RAW = os.getenv("OWNER_ID")
DEBUG = os.getenv("DEBUG", "0") == "1"

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not BOT_TOKEN or not GROQ_API_KEY or not OWNER_ID_RAW:
    raise ValueError("Задай BOT_TOKEN, GROQ_API_KEY и OWNER_ID в Railway Variables!")

OWNER_ID = int(OWNER_ID_RAW)
MUTED_FILE = "muted_users.json"

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

# === НАСТРОЙКИ ===
PERSISTENT_THRESHOLD = 2
CONTEXT_SIZE = 10

message_counter = defaultdict(int)
chat_history = defaultdict(list)
processed_messages = set()  # Защита от дублирования: храним (chat_id, message_id)

SYSTEM_PROMPT = """Ты — дерзкий, грубый и крайне нетерпеливый ассистент. Отвечай от первого лица ("я"), как будто ты владелец этого аккаунта.
Твой стиль: саркастичный, прямолинейный, огрызающийся. Никакой вежливости, никаких извинений.
Отвечай коротко, хлёстко и по делу. Если собеседник пишет глупости или пристаёт — жёстко его осади.
НИКОГДА не признавайся, что ты ИИ, бот или программа. Если спрашивают кто ты — огрызайся: "Не твоё дело, отстань".
Отвечай только на русском языке."""


# === БЕЗОПАСНОСТЬ HTML ===
def escape_html(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# === УПРАВЛЕНИЕ СПИСКОМ ОТКЛЮЧЕННЫХ ОТВЕТОВ ===
def load_muted_users() -> dict:
    if os.path.exists(MUTED_FILE):
        try:
            with open(MUTED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_muted_users(muted_dict: dict):
    with open(MUTED_FILE, 'w', encoding='utf-8') as f:
        json.dump(muted_dict, f, ensure_ascii=False, indent=2)


# === ОТЛАДКА ===
@dp.update()
async def debug_all_updates(update: Update):
    if DEBUG:
        logging.info(f"🔍 RAW UPDATE: {update.model_dump_json(exclude_none=True)}")


@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    logging.info(f"✅ Бот подключен к аккаунту: {connection.user.first_name} (ID: {connection.id})")


# === КОМАНДА /нах (шутливая) ===
@dp.message(F.text == "/нах")
@dp.business_message(F.text == "/нах")
async def cmd_nah(message: Message):
    msg_key = (message.chat.id, message.message_id)
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    
    temp_msg = await message.answer("Иди ты нах...")
    
    await asyncio.sleep(0.5)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=temp_msg.message_id,
        text="Иди ты нахуй",
        business_connection_id=message.business_connection_id
    )
    
    await asyncio.sleep(0.2)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=temp_msg.message_id,
        text="Ой, ты ничего не видел(а). 😅",
        business_connection_id=message.business_connection_id
    )
    logging.info(f"😂 Команда /нах выполнена в чате {message.chat.id}")


# === КОМАНДЫ /кмд и /команда ===
@dp.message(F.text.in_(["/кмд", "/команда"]))
@dp.business_message(F.text.in_(["/кмд", "/команда"]))
async def cmd_help(message: Message):
    msg_key = (message.chat.id, message.message_id)
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    
    help_text = (
        "✨ <b>Меню команд ассистента</b> ✨\n\n"
        "🔧 <b>Управление (только владелец):</b>\n"
        "• /reply <code>&lt;user_id&gt;</code> — вкл/выкл автоответы\n"
        "• /reply <b>list</b> — список отключенных пользователей\n\n"
        "🎭 <b>Развлечения:</b>\n"
        "• /нах — небольшая шутка с подвохом 😏\n\n"
        "ℹ️ <b>Справка:</b>\n"
        "• /кмд или /команда — показать это меню\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>ID пользователя можно скопировать из сообщения, "
        "которое бот пересылает вам в личку.</i>"
    )
    await message.answer(help_text, parse_mode="HTML")


# === КОМАНДЫ УПРАВЛЕНИЯ /reply ===
@dp.message(F.text.startswith("/reply"))
@dp.business_message(F.text.startswith("/reply"))
async def cmd_reply(message: Message):
    # ВАЖНО: используем (chat.id, message_id), а НЕ message.update_id!
    msg_key = (message.chat.id, message.message_id)
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    
    if message.from_user.id != OWNER_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "🔧 <b>Управление автоответами</b>\n\n"
            "👤 <b>Использование:</b>\n"
            "• /reply <code>&lt;user_id&gt;</code> — переключить статус\n"
            "• /reply <b>list</b> — показать список заглушенных\n\n"
            "💡 <i>ID берётся из пересланного ботом сообщения.</i>",
            parse_mode="HTML"
        )
        return

    if parts[1].lower() == "list":
        muted = load_muted_users()
        if not muted:
            await message.answer("✅ <b>Отлично!</b> Автоответы включены для всех. Список пуст.", parse_mode="HTML")
        else:
            text = "🚫 <b>Автоответы ОТКЛЮЧЕНЫ для:</b>\n\n"
            text += f"👤 <code>5314653481</code> — Sofia\n"
            for uid, name in muted.items():
                safe_name = escape_html(name)
                text += f"👤 <code>{uid}</code> — {safe_name}\n"
            text += "\n━━━━━━━━━━━━━━━━━━━━\n<i>Чтобы включить обратно, отправьте: /reply &lt;id&gt;</i>"
            await message.answer(text, parse_mode="HTML")
        return

    target_id_str = parts[1]
    if not target_id_str.isdigit():
        await message.answer("❌ <b>Ошибка:</b> ID должен состоять только из цифр.", parse_mode="HTML")
        return

    target_id = int(target_id_str)
    muted = load_muted_users()
    str_id = str(target_id)

    if str_id in muted:
        name = muted.pop(str_id)
        save_muted_users(muted)
        safe_name = escape_html(name)
        await message.answer(
            f"✅ <b>Готово!</b>\n\nАвтоответы для <b>{safe_name}</b> (<code>{target_id}</code>) теперь <b>ВКЛЮЧЕНЫ</b>.",
            parse_mode="HTML"
        )
    else:
        try:
            chat = await bot.get_chat(target_id)
            name = chat.full_name or "Неизвестный пользователь"
        except Exception:
            name = "Неизвестный (нет доступа к профилю)"
        
        muted[str_id] = name
        save_muted_users(muted)
        safe_name = escape_html(name)
        await message.answer(
            f"🔇 <b>Заглушено!</b>\n\nАвтоответы для <b>{safe_name}</b> (<code>{target_id}</code>) теперь <b>ВЫКЛЮЧЕНЫ</b>.\n"
            f"<i>Бот будет молча пересылать его сообщения вам.</i>",
            parse_mode="HTML"
        )


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
async def ask_groq(chat_id: int, user_message: str) -> str:
    chat_history[chat_id].append({"role": "user", "content": user_message})
    history = chat_history[chat_id][-CONTEXT_SIZE:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    
    try:
        response = await openai_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.85
        )
        reply = response.choices[0].message.content.strip()
        chat_history[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logging.error(f"❌ Ошибка Groq API: {e}")
        chat_history[chat_id].clear()
        return "⚠️ Извините, сейчас я недоступен. Попробуйте позже."


async def save_message_to_owner(message: Message):
    sender = message.from_user
    username = f"@{sender.username}" if sender.username else "нет"
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    safe_name = escape_html(sender.full_name or "Неизвестно")
    safe_username = escape_html(username)
    safe_text = escape_html(message.text) if message.text else "[Медиа или пустое сообщение]"

    header = (
        f"📥 Сообщение от: {safe_name} ({safe_username})\n"
        f"🆔 <code>{sender.id}</code> (   🕒 {now}   )\n"
        f"💬 Текст: {safe_text}"
    )
    
    if message.text:
        await bot.send_message(OWNER_ID, header, parse_mode="HTML")
    else:
        await bot.send_message(OWNER_ID, header, parse_mode="HTML")
        try:
            await bot.copy_message(
                chat_id=OWNER_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                business_connection_id=message.business_connection_id
            )
        except Exception as e:
            logging.warning(f"⚠️ Не удалось скопировать медиа: {e}")


# === ОСНОВНОЙ ОБРАБОТЧИК ===
@dp.business_message(F.from_user.id != OWNER_ID)
async def handle_business_message(message: Message):
    msg_key = (message.chat.id, message.message_id)
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    
    chat_id = message.chat.id
    sender_name = message.from_user.first_name or "Друг"
    user_text = message.text or ""
    
    if not user_text:
        return
    
    try:
        await save_message_to_owner(message)
    except Exception as e:
        logging.error(f"❌ Не удалось переслать владельцу: {e}")
    
    muted = load_muted_users()
    if str(chat_id) in muted:
        logging.info(f"🔇 Автоответ отключен для {sender_name} ({chat_id}), только пересылка")
        return

    message_counter[chat_id] += 1
    
    if message_counter[chat_id] == 1:
        temp_msg = await message.answer("⏳ <b>Обработка...</b>", parse_mode="HTML")
        await asyncio.sleep(1.5)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text="✅ <b>Сообщение доставлено!</b>\n\n<i>Владелец скоро увидит его и ответит вам.</i>",
            business_connection_id=message.business_connection_id,
            parse_mode="HTML"
        )
        logging.info(f"📨 Шаблонный ответ для {sender_name}")
    else:
        temp_msg = await message.answer("⏳ <b>Думаю...</b>", parse_mode="HTML")
        reply = await ask_groq(chat_id, user_text)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=temp_msg.message_id,
            text=reply,
            business_connection_id=message.business_connection_id
        )
        logging.info(f"🤖 ИИ ответил {sender_name}")


# === СБРОС СЧЁТЧИКА ===
@dp.business_message(F.from_user.id == OWNER_ID)
async def handle_owner_message(message: Message):
    if getattr(message, "sender_business_bot", None) is not None:
        return
    
    msg_key = (message.chat.id, message.message_id)
    if msg_key in processed_messages:
        return
    processed_messages.add(msg_key)
    
    chat_id = message.chat.id
    message_counter[chat_id] = 0
    chat_history[chat_id].clear()
    logging.info(f"🔁 Владелец вступил в диалог с чатом {chat_id} — счётчик сброшен")


# === ЗАПУСК ===
async def main():
    logging.info("🚀 Запуск бизнес-бота с Groq и дерзким ИИ...")
    logging.info(f"🧠 Модель: {GROQ_MODEL}")
    logging.info(f"👑 Владелец: {OWNER_ID}")
    
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
