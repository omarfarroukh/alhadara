from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update
from django.conf import settings
from django.core.cache import cache
import logging
import urllib.parse

logger = logging.getLogger(__name__)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command with or without parameters.
    Supports both deep-linked file downloads and plain /start.
    """
    message = update.message
    if not message:
        logger.warning("Received update with no message.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "unknown"
    text = message.text or ""
    logger.info(f"START from user {user_id} in chat {chat_id}: {text!r}")

    # --- Parameter extraction ---
    param = None
    if context.args:
        param = context.args[0]
    elif text.startswith("/start "):
        param = text[7:]
    logger.debug(f"Parsed parameter: {param!r}")

    # --- Download link handling ---
    if param and param.startswith("download_"):
        short_id = param[len("download_") :]
        cache_key = f"telegram_file_{short_id}"
        file_id = cache.get(cache_key)

        if not file_id:
            logger.error(f"Cache miss for short_id={short_id}")
            await message.reply_text(
                "❌ Link expired or invalid.\n"
                "Please request a fresh download link from the app."
            )
            return

        logger.info(f"Cache hit → file_id={file_id}")
        try:
            # Telegram accepts document, audio, video, voice, photo, etc.
            await context.bot.send_document(chat_id=chat_id, document=file_id)
            logger.info(f"File delivered to {chat_id}")
            return
        except Exception as exc:
            logger.exception(f"Delivery failed for file_id={file_id}")
            await message.reply_text(
                "❌ Could not send the file.\n"
                "Please try again later or contact support."
            )
            return

    if param:
        logger.warning(f"Unknown /start parameter: {param!r}")
        await message.reply_text("❌ Invalid download link format.")
        return

    # --- Plain /start ---
    await message.reply_text(
        "👋 Welcome to the File Storage Bot!\n\n"
        "• Tap a download link in your app to receive the file here.\n"
        "• If you just added me, click the link again to retrieve your file."
    )

async def handle_fallback_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback handler for manual text input"""
    message = update.message
    if not message:
        return
    
    text = message.text or ""
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "unknown"
    
    logger.info(f"Received fallback message from user {user_id} in chat {chat_id}: '{text}'")
    
    # Check if it's a manual download command
    if text.startswith("download_"):
        short_id = text[len("download_"):]
        logger.info(f"Attempting to resolve short_id from fallback: {short_id}")
        
        # Get the actual file_id from cache
        cache_key = f"telegram_file_{short_id}"
        file_id = cache.get(cache_key)
        
        if not file_id:
            logger.error(f"File ID not found for short_id: {short_id}")
            await message.reply_text("Sorry, this download link has expired or is invalid.")
            return
        
        logger.info(f"Resolved file_id from fallback: {file_id}")
        try:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_id
            )
            logger.info(f"File sent successfully to chat {chat_id}")
            return
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            await message.reply_text("Sorry, failed to send the file. Please check the link or contact support.")
            return
    else:
        await message.reply_text("Unknown command. Use /start or a valid download link.")

def start_bot():
    """Start the bot with async polling"""
    application = Application.builder().token(settings.TELEGRAM_FILE_BOT_TOKEN).build()
    
    # Add debug logging
    import logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", handle_start))
    
    # Add fallback handler for non-command messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fallback_download))
    
    print("Bot started polling...")
    application.run_polling()

async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug handler to log all incoming messages"""
    message = update.message
    if message:
        logger.info(f"DEBUG: Received message: '{message.text}', args: {context.args}")
    return