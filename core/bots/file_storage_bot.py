from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram import Update
from django.conf import settings
from django.core.cache import cache
import logging
import urllib.parse

logger = logging.getLogger(__name__)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with or without parameters"""
    message = update.message
    if not message:
        logger.warning("No message in update")
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else "unknown"
    
    # Get the full command text
    text = message.text or ""
    logger.info(f"Received start command from user {user_id} in chat {chat_id}: '{text}'")
    
    # Try both context.args and manual parsing
    param = None
    if len(context.args) > 0:
        param = context.args[0]
        logger.info(f"Parameter from context.args: '{param}'")
    elif text.startswith("/start "):
        param = text[7:]  # everything after "/start "
        logger.info(f"Parameter from manual parsing: '{param}'")
    
    if param and param.startswith("download_"):
        short_id = param[len("download_"):]
        logger.info(f"Attempting to resolve short_id: {short_id}")
        
        # Get the actual file_id from cache
        cache_key = f"telegram_file_{short_id}"
        file_id = cache.get(cache_key)
        
        if not file_id:
            logger.error(f"File ID not found for short_id: {short_id}")
            await message.reply_text("Sorry, this download link has expired or is invalid.")
            return
        
        logger.info(f"Resolved file_id: {file_id}")
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
    elif param:
        logger.info(f"Unknown parameter: {param}")
        await message.reply_text("Invalid download link format.")
        return
    else:
        # No parameters, just plain /start
        logger.info("Received plain /start command")
        await message.reply_text(
            "Welcome to the File Storage Bot!\n\n"
            "To download a file, use the link provided in your app or contact support.\n\n"
            "If you just started the bot, please click your download link again to receive your file."
        )
        return

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