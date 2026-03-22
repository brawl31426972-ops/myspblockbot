import logging
import asyncio
import html
import io
import random
import string
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReplyKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler
from telegram.error import BadRequest, Forbidden

import mainconfig
import maindatabase

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- СОСТОЯНИЯ ДЛЯ ОПРОСА (АПЕЛЛЯЦИЯ) ---
STATE_Q1, STATE_Q2, STATE_Q3 = range(3)

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id: int, context: CallbackContext) -> bool:
    try:
        member = await context.bot.get_chat_member(mainconfig.CHANNEL_USERNAME, user_id)
        if member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return True

# --- МЕНЮ ---
def get_user_keyboard(is_active: bool):
    if is_active:
        keyboard = [["❓ Помощь"]]
    else:
        keyboard = [
            ["📝 Написать поддержку"],
            ["❓ Помощь"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_banned_keyboard():
    keyboard = [
        ["🚫 Заявка на разбан"],
        ["❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- ЛОГИРОВАНИЕ ---
async def log_action(context: CallbackContext, user, action_text: str, message_content: str = None, file=None, topic_id=None):
    try:
        time_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        name = html.escape(user.full_name) if user else "System"
        username = f"@{user.username}" if user and user.username else "нет"
        user_id = user.id if user else "N/A"

        text = f"<b>{action_text}</b>\n\n"
        text += f"👤 <b>Имя:</b> {name}\n"
        text += f"📛 <b>User:</b> {username}\n"
        text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        text += f"⏰ <b>Время:</b> {time_str}"
        
        if message_content:
            text += f"\n\n💬 <b>Текст:</b>\n{message_content}"

        target_topic = topic_id if topic_id else mainconfig.LOG_TOPIC_ID
        chat_id = mainconfig.SUPPORT_GROUP_ID
        
        if file:
            await context.bot.send_document(chat_id, message_thread_id=target_topic, document=file, caption=text, parse_mode='HTML')
        else:
            photos = await context.bot.get_user_profile_photos(user_id, limit=1) if user else None
            photo_file = None
            if photos and photos.photos:
                photo_file = photos.photos[0][-1].file_id 
            
            if photo_file:
                await context.bot.send_photo(chat_id, message_thread_id=target_topic, photo=photo_file, caption=text, parse_mode='HTML')
            else:
                await context.bot.send_message(chat_id, message_thread_id=target_topic, text=text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка лога: {e}")

# --- ВСПОМОГАТЕЛЬНЫЕ ---
def get_user_header_text(user, time_str):
    name = html.escape(user.full_name)
    header = f"👤 <b>{name}</b>"
    if user.username: header += f" | @{user.username}"
    header += f"\n🆔 <code>{user.id}</code> | ⏰ {time_str}"
    return header

def get_admin_header_text(admin, time_str):
    return f"👨‍💻 <b>Админ:</b> {html.escape(admin.full_name)} | ⏰ {time_str}"

def get_content_type_name(message):
    if message.photo: return "📷 Фото"
    if message.video: return "🎥 Видео"
    if message.audio: return "🎵 Аудио"
    if message.voice: return "🎙 Голосовое"
    if message.video_note: return "🍩 Кружок"
    if message.sticker: return f"🎭 Стикер {message.sticker.emoji or ''}"
    if message.document: return "📄 Документ"
    if message.contact: return "👤 Контакт"
    if message.location: return "📍 Локация"
    if message.text: return "📝 Текст"
    return "📎 Вложение"

async def generate_txt_file(user_data, logs):
    content = f"ЧАТ С ПОЛЬЗОВАТЕЛЕМ: {user_data[2]} (ID: {user_data[0]})\n"
    content += f"Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n" + "="*40 + "\n\n"
    for role, msg_text, timestamp in logs:
        time_str = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
        prefix = f"[{time_str}] 👤 User:" if role == 'USER' else f"[{time_str}] 👨‍💻 Admin:"
        content += f"{prefix}\n{msg_text}\n\n"
    return io.BytesIO(content.encode('utf-8'))

async def delete_topic_later(context: CallbackContext, topic_id: int, delay_hours: int = 8):
    await asyncio.sleep(delay_hours * 3600)
    try:
        await context.bot.delete_forum_topic(mainconfig.SUPPORT_GROUP_ID, topic_id)
    except: pass

# --- ОБРАБОТКА ЗАЯВКИ НА РАЗБАН ---
async def start_appeal(update: Update, context: CallbackContext):
    user = update.effective_user
    if not await maindatabase.is_banned(user.id):
        await update.message.reply_text("✅ Вы не заблокированы!", reply_markup=get_user_keyboard(False))
        return ConversationHandler.END
    
    await update.message.reply_text("📝 <b>Начинаем процедуру подачи заявки на разбан.</b>\n\n" + mainconfig.APPEAL_QUESTIONS[0], parse_mode='HTML')
    return STATE_Q1

async def receive_q1(update: Update, context: CallbackContext):
    context.user_data['appeal_a1'] = update.message.text
    await update.message.reply_text(mainconfig.APPEAL_QUESTIONS[1], parse_mode='HTML')
    return STATE_Q2

async def receive_q2(update: Update, context: CallbackContext):
    context.user_data['appeal_a2'] = update.message.text
    await update.message.reply_text(mainconfig.APPEAL_QUESTIONS[2], parse_mode='HTML')
    return STATE_Q3

async def receive_q3(update: Update, context: CallbackContext):
    user = update.effective_user
    context.user_data['appeal_a3'] = update.message.text
    
    appeal_id = await maindatabase.get_appeal_id()
    
    text_content = f"ЗАЯВКА НА РАЗБАН #{appeal_id}\n"
    text_content += f"ОТ: {user.full_name} (@{user.username}) ID: {user.id}\n"
    text_content += f"ВРЕМЯ: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
    text_content += "="*30 + "\n\n"
    
    text_content += f"{mainconfig.APPEAL_QUESTIONS[0]}\n➡️ {context.user_data['appeal_a1']}\n\n"
    text_content += f"{mainconfig.APPEAL_QUESTIONS[1]}\n➡️ {context.user_data['appeal_a2']}\n\n"
    text_content += f"{mainconfig.APPEAL_QUESTIONS[2]}\n➡️ {context.user_data['appeal_a3']}\n"
    
    file = io.BytesIO(text_content.encode('utf-8'))
    filename = f"ЗАЯВКА_{appeal_id}_ОТ_{user.id}.txt"
    file.name = filename
    
    try:
        await context.bot.send_document(
            mainconfig.SUPPORT_GROUP_ID,
            message_thread_id=mainconfig.APPEAL_TOPIC_ID,
            document=InputFile(file, filename=filename),
            caption=f"🆕 <b>Новая заявка на разбан #{appeal_id}</b>",
            parse_mode='HTML'
        )
        await update.message.reply_text("✅ Ваша заявка принята! Ожидайте решения.", reply_markup=get_banned_keyboard())
    except Exception as e:
        logger.error(f"Ошибка отправки заявки: {e}")
        await update.message.reply_text("❌ Ошибка подачи заявки.", reply_markup=get_banned_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_appeal(update: Update, context: CallbackContext):
    await update.message.reply_text("❌ Отменено.", reply_markup=get_banned_keyboard())
    return ConversationHandler.END

# --- ПОЛЬЗОВАТЕЛЬ ---

async def cmd_start(update: Update, context: CallbackContext):
    user = update.effective_user
    
    if await maindatabase.is_banned(user.id):
        await update.message.reply_text(
            mainconfig.TEXT_BANNED + "\n\nУ вас есть возможность подать апелляцию.", 
            parse_mode='HTML',
            reply_markup=get_banned_keyboard()
        )
        return

    if not await check_subscription(user.id, context):
        keyboard = [[InlineKeyboardButton("🔄 Проверить подписку", callback_data=f"check_sub_{user.id}")]]
        await update.message.reply_text(mainconfig.TEXT_NOT_SUBSCRIBED, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    user_data = await maindatabase.get_or_create_user(user.id, user.username, user.full_name)
    topic_id = user_data[3]

    if topic_id:
        await update.message.reply_text(mainconfig.TEXT_ALREADY_ACTIVE, parse_mode='HTML', reply_markup=get_user_keyboard(is_active=True))
    else:
        await update.message.reply_text(mainconfig.TEXT_WELCOME, parse_mode='HTML', reply_markup=get_user_keyboard(is_active=False))

# Добавлена команда /help
async def cmd_help(update: Update, context: CallbackContext):
    # Проверяем бан и подписку для единообразия, или просто шлем текст
    await update.message.reply_text(mainconfig.TEXT_GUIDE.format(channel=mainconfig.CHANNEL_USERNAME), parse_mode='HTML')

async def subscription_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[2])
    
    if await check_subscription(user_id, context):
        try:
            await query.message.delete()
        except: pass
        
        if await maindatabase.is_banned(user_id):
             await context.bot.send_message(user_id, mainconfig.TEXT_BANNED, parse_mode='HTML', reply_markup=get_banned_keyboard())
        else:
             user_data = await maindatabase.get_or_create_user(user_id, query.from_user.username, query.from_user.full_name)
             topic_id = user_data[3]
             await context.bot.send_message(user_id, "✅ Подписка подтверждена!\n" + mainconfig.TEXT_WELCOME, parse_mode='HTML', reply_markup=get_user_keyboard(is_active=bool(topic_id)))
    else:
        await query.answer("Вы не подписались на канал!", show_alert=True)

async def handle_user_text_buttons(update: Update, context: CallbackContext):
    text = update.message.text
    user = update.effective_user
    
    if not await check_subscription(user.id, context):
        keyboard = [[InlineKeyboardButton("🔄 Проверить подписку", callback_data=f"check_sub_{user.id}")]]
        await update.message.reply_text(mainconfig.TEXT_NOT_SUBSCRIBED, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if await maindatabase.is_banned(user.id):
        if text == "❓ Помощь":
            await update.message.reply_text(mainconfig.TEXT_GUIDE.format(channel=mainconfig.CHANNEL_USERNAME), parse_mode='HTML')
        return

    user_data = await maindatabase.get_or_create_user(user.id, user.username, user.full_name)
    topic_id = user_data[3]

    if text == "❓ Помощь":
        await update.message.reply_text(mainconfig.TEXT_GUIDE.format(channel=mainconfig.CHANNEL_USERNAME), parse_mode='HTML')
    elif text == "📝 Написать поддержку":
        if topic_id:
            await update.message.reply_text("⚠️ Диалог уже активен.", reply_markup=get_user_keyboard(True))
        else:
            await update.message.reply_text("✍️ Напишите ваш вопрос.", reply_markup=get_user_keyboard(False))
    else:
        await handle_user_message(update, context)

async def handle_user_message(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    message = update.message
    
    if message.text and message.text.startswith(("❓", "📝", "🚫")): return
    
    if not await check_subscription(user_id, context):
        keyboard = [[InlineKeyboardButton("🔄 Проверить подписку", callback_data=f"check_sub_{user_id}")]]
        await update.message.reply_text(mainconfig.TEXT_NOT_SUBSCRIBED, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if await maindatabase.is_banned(user_id): return

    user_data = await maindatabase.get_or_create_user(user_id, user.username, user.full_name)
    topic_id = user_data[3]
    
    keyboard = [[InlineKeyboardButton("🛑 Завершить", callback_data=f"stop_{user_id}"), InlineKeyboardButton("🚫 Бан", callback_data=f"ban_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if not topic_id:
        try:
            forum_topic = await context.bot.create_forum_topic(mainconfig.SUPPORT_GROUP_ID, name=f"{user.full_name} (ID: {user_id})", icon_color=0x6FB9F0)
            topic_id = forum_topic.message_thread_id
            await maindatabase.set_topic(user_id, topic_id)
            await log_action(context, user, "🆕 НАЧАЛО ДИАЛОГА")
            await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text=f"🆕 <b>Новый диалог</b>", parse_mode='HTML')
            await message.reply_text("✅ Диалог начат.", reply_markup=get_user_keyboard(is_active=True))
        except Exception as e:
            logger.error(f"Ошибка создания топика: {e}")
            return

    time_str = datetime.now().strftime("%H:%M:%S")
    
    # --- Формирование шапки ---
    header_text = get_user_header_text(user, time_str)
    
    # --- Обработка ответа (Reply) ---
    quote_text = ""
    if message.reply_to_message:
        replied = message.reply_to_message
        if replied.from_user.is_bot:
            admin_time = ""
            txt = replied.text or replied.caption
            if txt:
                match = re.search(r'⏰ (\d{2}:\d{2}:\d{2})', txt)
                if match: admin_time = f" | ⏰ {match.group(1)}"
            
            content_type = get_content_type_name(replied)
            content_prev = ""
            if content_type == "📝 Текст":
                if txt:
                    parts = txt.split('\n\n')
                    if len(parts) > 1: content_prev = parts[-1][:50]
            else:
                if replied.caption: content_prev = replied.caption[:30]
            
            admin_name = "Админ"
            if txt and "Админ:" in txt:
                try:
                    line1 = txt.split('\n')[0]
                    admin_name = line1.split("Админ:")[1].split("|")[0].strip()
                except: pass
            
            q_content_display = f"{content_type}"
            if content_prev: q_content_display += f": {content_prev}"
            
            quote_text = f"↩️ <b>Ответ на:</b> 👨‍💻 {html.escape(admin_name)}{admin_time}\n"
            quote_text += f"<blockquote expandable>{q_content_display}</blockquote>\n\n"
    
    # --- Отправка контента ---
    try:
        if message.text:
            final_text = f"{header_text}\n\n{quote_text}{message.text_html}"
            await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text=final_text, parse_mode='HTML', reply_markup=reply_markup)
            log_content = message.text
        
        else:
            full_caption = f"{header_text}\n\n{quote_text}"
            if message.caption:
                full_caption += f"\n{message.caption_html}"
            
            if message.sticker:
                await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text=full_caption, parse_mode='HTML')
                await context.bot.send_sticker(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, sticker=message.sticker.file_id, reply_markup=reply_markup)
            else:
                await message.copy(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, caption=full_caption[:1024], parse_mode='HTML', reply_markup=reply_markup)
            
            log_content = "[Медиа]"

        await log_action(context, user, "💬 СООБЩЕНИЕ", message_content=log_content)
        await maindatabase.log_message(user_id, "USER", log_content)
        
        await message.reply_text("✅ Доставлено")
        
    except Exception as e: 
        logger.error(f"Ошибка: {e}")

# --- АДМИН ---

async def handle_admin_reply(update: Update, context: CallbackContext):
    if update.effective_chat.id != mainconfig.SUPPORT_GROUP_ID: return
    if not update.message.is_topic_message: return
    if update.message.from_user.is_bot: return
    
    topic_id = update.message.message_thread_id
    message = update.message
    admin = update.effective_user

    # --- ЛОГИКА РАЗБАНА ---
    if topic_id == mainconfig.UNBAN_TOPIC_ID:
        text = message.text
        if text:
            parts = text.split()
            if len(parts) == 2:
                code_candidate, account_candidate = parts[0], parts[1]
                if account_candidate == mainconfig.VERIFICATION_ACCOUNT:
                    code_data = await maindatabase.get_unban_code(code_candidate)
                    if code_data:
                        target_user_id = code_data[0]
                        await maindatabase.unban_user(target_user_id)
                        try: await context.bot.send_message(target_user_id, "✅ Вы разбанены.", parse_mode='HTML')
                        except: pass
                        await message.reply_text(f"✅ Разбанен {target_user_id}.")
                        
                        class FakeUser: pass
                        u = FakeUser(); u.id = target_user_id; u.full_name = f"ID {target_user_id}"; u.username = None
                        await log_action(context, u, "✅ РАЗБАН", message_content=f"Админ: {admin.full_name}")
        return

    # --- ЛОГИКА ОТВЕТА ЮЗЕРУ ---
    user_data = await maindatabase.get_user_by_topic(topic_id)
    if not user_data: return
    user_id = user_data[0]
    user_name = user_data[2]
    user_username = user_data[1]
    
    time_str = datetime.now().strftime("%H:%M:%S")
    header = get_admin_header_text(admin, time_str)
    
    # --- Формируем цитату (если админ отвечает на сообщение) ---
    quote_text = ""
    if message.reply_to_message:
        replied = message.reply_to_message
        
        # Если отвечаем на "корневое" сообщение топика (заголовок), то считаем, что это не ответ
        if replied.message_id == topic_id:
            pass
            
        # Проверяем, на кого отвечаем
        elif replied.from_user.is_bot:
            # Отвечаем на сообщение ПОЛЬЗОВАТЕЛЯ
            
            # Ищем время
            msg_time = ""
            txt = replied.text or replied.caption
            if txt:
                match = re.search(r'⏰ (\d{2}:\d{2}:\d{2})', txt)
                if match: msg_time = f" | ⏰ {match.group(1)}"
            
            # Автор
            user_display = html.escape(user_name)
            if user_username:
                user_display += f" (@{user_username})"
                
            author_display = f"👤 {user_display} | ID: {user_id}{msg_time}"
            
            # Контент
            content_type = get_content_type_name(replied)
            content_prev = ""
            
            if content_type == "📝 Текст":
                if txt:
                    parts = txt.split('\n\n')
                    clean_text = '\n\n'.join(parts[1:])
                    content_prev = clean_text[:100]
            else:
                if replied.caption: content_prev = replied.caption[:50]
            
            q_display = f"{content_type}"
            if content_prev: q_display += f": {content_prev}"
            
            quote_text = f"↩️ <b>Ответ на:</b> {author_display}\n"
            quote_text += f"<blockquote expandable>{q_display}</blockquote>\n\n"
            
        else:
            # Отвечаем на сообщение ДРУГОГО АДМИНА
            author_display = f"👨‍💻 {html.escape(replied.from_user.full_name)}"
            content_type = get_content_type_name(replied)
            content_prev = (replied.text or replied.caption or "")[:100]
            
            q_display = f"{content_type}"
            if content_prev: q_display += f": {content_prev}"
            
            quote_text = f"↩️ <b>Ответ на:</b> {author_display}\n"
            quote_text += f"<blockquote expandable>{q_display}</blockquote>\n\n"

    keyboard = [[InlineKeyboardButton("🛑 Завершить", callback_data=f"stop_{user_id}"), InlineKeyboardButton("🚫 Бан", callback_data=f"ban_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # 1. Отправляем шапку админа в ЛС юзеру
        await context.bot.send_message(user_id, header, parse_mode='HTML')

        # 2. Обрабатываем ответ
        if message.text:
            # Текст
            user_text = f"{quote_text}{message.text_html}"
            await context.bot.send_message(user_id, user_text, parse_mode='HTML')
            
            # Дублируем в группу (не удаляя оригинал)
            group_text = f"{header}\n\n{quote_text}{message.text_html}"
            await context.bot.send_message(
                mainconfig.SUPPORT_GROUP_ID, 
                message_thread_id=topic_id, 
                text=group_text, 
                parse_mode='HTML', 
                reply_markup=reply_markup
            )
            
            log_content = message.text
        
        else:
            # Медиа
            if quote_text:
                 await context.bot.send_message(user_id, quote_text, parse_mode='HTML')
            
            await message.copy(user_id)
            
            # Дублируем в группу
            if quote_text:
                await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text=quote_text, parse_mode='HTML')
            
            if message.sticker:
                await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text=header, parse_mode='HTML')
                await context.bot.send_sticker(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, sticker=message.sticker.file_id, reply_markup=reply_markup)
            else:
                await message.copy(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, caption=header, parse_mode='HTML', reply_markup=reply_markup)
            
            log_content = "[Медиа]"

        await log_action(context, admin, f"📤 ОТВЕТ (Юзеру {user_id})", message_content=log_content)
        await maindatabase.log_message(user_id, "ADMIN", log_content)
        
    except Forbidden:
        await context.bot.send_message(mainconfig.SUPPORT_GROUP_ID, message_thread_id=topic_id, text="❌ Юзер заблокировал бота.")
    except Exception as e:
        logger.error(f"Ошибка отправки админа: {e}")

# --- UNBAN SYSTEM ---

async def cmd_unban(update: Update, context: CallbackContext):
    if update.effective_chat.id != mainconfig.SUPPORT_GROUP_ID: return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /unban USER_ID")
        return
    
    try: target_user_id = int(args[0])
    except:
        await update.message.reply_text("Неверный ID.")
        return

    user_data = await maindatabase.get_or_create_user(target_user_id, "", "")
    if not user_data or user_data[4] == 0:
        await update.message.reply_text(f"✅ {target_user_id} не забанен.")
        return

    code = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    await maindatabase.add_unban_code(code, target_user_id, update.effective_user.id)
    
    try:
        await context.bot.send_message(mainconfig.ADMIN_ID, f"🔐 Код для разбана {target_user_id}: <code>{code}</code>\n\nОтправьте: <code>{code} {mainconfig.VERIFICATION_ACCOUNT}</code> в топик {mainconfig.UNBAN_TOPIC_ID}", parse_mode='HTML')
        await update.message.reply_text("⏳ Код отправлен в ЛС.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка ЛС: {e}")

# --- LOGIC FINISH ---

async def stop_dialog_logic(user_id: int, context: CallbackContext, source_msg):
    user_data = await maindatabase.get_or_create_user(user_id, "", "")
    topic_id = user_data[3]
    if not topic_id: return

    logs = await maindatabase.get_chat_logs(user_id)
    if logs:
        txt_file = await generate_txt_file(user_data, logs)
        filename = f"log_{user_id}.txt"
        txt_file.name = filename
        class FakeUser: pass
        u = FakeUser(); u.id = user_id; u.full_name = user_data[2]; u.username = user_data[1]
        await log_action(context, u, "📁 ФАЙЛ ПЕРЕПИСКИ", file=InputFile(txt_file, filename))
    
    await maindatabase.clear_chat_logs(user_id)

    try: await context.bot.send_message(user_id, "🛑 Диалог завершен администратором.", parse_mode='HTML', reply_markup=get_user_keyboard(is_active=False))
    except: pass

    try: await context.bot.edit_forum_topic(mainconfig.SUPPORT_GROUP_ID, topic_id, name=f"📁 Закрыто: {user_data[2]}")
    except: pass
    
    await maindatabase.clear_topic(user_id)
    asyncio.create_task(delete_topic_later(context, topic_id, 8))
    
    class FakeUser: pass
    u = FakeUser(); u.id = user_id; u.full_name = user_data[2]; u.username = user_data[1]
    await log_action(context, u, "🛑 ДИАЛОГ ЗАВЕРШЕН (Админом)")

    try: await source_msg.reply_text("🛑 Завершено.")
    except: pass

async def admin_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("check_sub_"):
        await subscription_button(update, context)
        return

    action = data.split('_')[0]
    user_id = int(data.split('_')[1])
    
    user_data = await maindatabase.get_or_create_user(user_id, "", "")
    topic_id = user_data[3]

    if action == "stop":
        await stop_dialog_logic(user_id, context, query.message)
    
    elif action == "ban":
        await maindatabase.ban_user(user_id)
        try: await context.bot.send_message(user_id, "⛔ Заблокирован.", parse_mode='HTML', reply_markup=get_banned_keyboard())
        except: pass
        
        class FakeUser: pass
        u = FakeUser(); u.id = user_id; u.full_name = user_data[2]; u.username = user_data[1]
        await log_action(context, u, "🚫 БАН")
        
        await query.message.reply_text(f"🚫 Забанен {user_id}.")

# --- MAIN ---
def main():
    asyncio.run(maindatabase.init_db())
    app = Application.builder().token(mainconfig.BOT_TOKEN).build()

    appeal_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚫 Заявка на разбан$"), start_appeal)],
        states={
            STATE_Q1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_q1)],
            STATE_Q2: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_q2)],
            STATE_Q3: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_q3)],
        },
        fallbacks=[CommandHandler('cancel', cancel_appeal)],
        per_user=True
    )

    app.add_handler(appeal_handler)
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help)) # Добавлена команда /help
    
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_user_text_buttons))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    
    app.add_handler(CommandHandler("unban", cmd_unban, filters=filters.Chat(mainconfig.SUPPORT_GROUP_ID)))
    
    app.add_handler(MessageHandler(filters.Chat(mainconfig.SUPPORT_GROUP_ID) & filters.IS_TOPIC_MESSAGE, handle_admin_reply))
    
    app.add_handler(CallbackQueryHandler(admin_buttons))

    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()