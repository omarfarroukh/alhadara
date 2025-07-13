import asyncio
import urllib.parse
import hashlib
import uuid
from telegram import Bot
from django.conf import settings
from django.core.cache import cache

def upload_to_telegram(file):
    """Uploads a file to Telegram and returns file_id + download link."""
    bot = Bot(token=settings.TELEGRAM_FILE_BOT_TOKEN)
    async def send():
        try:
            msg = await bot.send_document(
                chat_id=settings.TELEGRAM_FILE_CHAT_ID,
                document=file,
                filename=getattr(file, 'name', 'file')
            )
            return msg
        except Exception as e:
            print(f"Telegram upload failed: {e}")
            return None
    msg = asyncio.run(send())
    if not msg or not getattr(msg, 'document', None):
        raise Exception("Telegram upload failed or returned no document.")
    
    # Create a shorter identifier for the deep link
    # Option 1: Use a hash of the file_id
    short_id = hashlib.md5(msg.document.file_id.encode()).hexdigest()[:12]
    
    # Option 2: Use a random UUID (uncomment if you prefer this)
    # short_id = str(uuid.uuid4())[:12]
    
    # Store the mapping in cache/database for 24 hours
    cache_key = f"telegram_file_{short_id}"
    cache.set(cache_key, msg.document.file_id, timeout=86400)  # 24 hours
    
    return {
        "file_id": msg.document.file_id,  # Store the original file_id
        "download_link": f"https://t.me/{settings.TELEGRAM_FILE_BOT_USERNAME}?start=download_{short_id}",
    }