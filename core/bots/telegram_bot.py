# core/bots/telegram_bot.py
from telegram.ext import Application, CommandHandler
from django.conf import settings
from django.core.cache import cache
from core.models import User
from django_rq import enqueue
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)

# Create thread-safe database access
get_user = sync_to_async(User.objects.get, thread_sensitive=True)
save_user = sync_to_async(lambda user: user.save(), thread_sensitive=True)

async def start(update, context):
    token = context.args[0] if context.args else None
    if token:
        phone = cache.get(f"user_verification:{token}")
        if phone:
            try:
                user = await get_user(phone=phone)
                user.telegram_chat_id = update.effective_chat.id
                await save_user(user)
                
                enqueue("core.tasks.send_telegram_pin", update.effective_chat.id, token)
                await update.message.reply_text("✅ Verification started! Check your PIN.")
            except User.DoesNotExist:
                await update.message.reply_text("⚠️ User not found")
        else:
            await update.message.reply_text("⚠️ Invalid or expired token.")
    else:
        await update.message.reply_text("Hi! Use the app link to verify.")

def setup_bot():
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    return application