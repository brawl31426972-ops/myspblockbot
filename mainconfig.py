import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

LOG_TOPIC_ID = int(os.getenv("LOG_TOPIC_ID"))
LOG_FILE_TOPIC_ID = int(os.getenv("LOG_FILE_TOPIC_ID"))
UNBAN_TOPIC_ID = int(os.getenv("UNBAN_TOPIC_ID"))
APPEAL_TOPIC_ID = int(os.getenv("APPEAL_TOPIC_ID"))

VERIFICATION_ACCOUNT = os.getenv("VERIFICATION_ACCOUNT")
CREATOR_LINK = os.getenv("CREATOR_LINK")


TEXT_WELCOME = "👋 Напишите ваш вопрос, чтобы начать диалог."
TEXT_ALREADY_ACTIVE = "⚠️ У вас уже есть активный диалог."
TEXT_BANNED = "⛔ Вы заблокированы."

TEXT_NOT_SUBSCRIBED = (
    "🚫 <b>Доступ запрещен</b>\n\n"
    "Для использования бота необходимо быть подписанным на наш канал.\n"
    f'👉 Подпишитесь: <a href="https://t.me/{CHANNEL_USERNAME.replace("@", "")}">{CHANNEL_USERNAME}</a>\n\n'
    "После подписки нажмите кнопку ниже для проверки."
)

APPEAL_QUESTIONS = [
    "❓ <b>Вопрос 1:</b>\nКак вы думаете, почему вас заблокировали?",
    "❓ <b>Вопрос 2:</b>\nПочему мы должны снять блокировку?",
    "❓ <b>Вопрос 3:</b>\nНапишите ваш ID или дополнительную информацию, которая может помочь."
]

TEXT_GUIDE = (
    "📖 <b>Инструкция по использованию бота</b>\n\n"
    "1️⃣ <b>Как начать?</b>\n"
    "Нажмите кнопку <b>«📝 Написать поддержку»</b> внизу или просто отправьте любое сообщение.\n\n"
    "2️⃣ <b>Как это работает?</b>\n"
    "Ваше сообщение попадает администраторам в закрытый чат.\n\n"
    "3️⃣ <b>Если вас забанили:</b>\n"
    "Вы можете подать заявку на разбан через меню бота.\n\n"
    f"• Вы должны оставаться подписанным на канал {CHANNEL_USERNAME}."
)
