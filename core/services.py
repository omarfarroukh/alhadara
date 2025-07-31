import asyncio
import urllib.parse
import hashlib
import uuid
import time
from telegram import Bot
from telegram.request import HTTPXRequest
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

def upload_to_telegram(file):
    """Uploads a file to Telegram and returns file_id + download link."""
    
    # Get file size for dynamic timeout calculation
    file_size = getattr(file, 'size', 0)
    if hasattr(file, 'seek') and hasattr(file, 'tell'):
        # For file-like objects, get size by seeking
        current_pos = file.tell()
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(current_pos)  # Seek back to original position
    
    # Calculate dynamic timeouts based on file size
    # Base timeout of 60s + 30s per MB
    base_timeout = 60
    size_in_mb = file_size / (1024 * 1024)
    dynamic_timeout = base_timeout + (size_in_mb * 30)
    
    # Cap the timeout at reasonable limits
    read_timeout = min(max(dynamic_timeout, 60), 600)  # 1-10 minutes
    write_timeout = min(max(dynamic_timeout, 60), 600)  # 1-10 minutes
    
    logger.info(f"File size: {file_size} bytes ({size_in_mb:.2f} MB)")
    logger.info(f"Using timeouts: read={read_timeout}s, write={write_timeout}s")
    
    # Create request with dynamic timeouts
    request = HTTPXRequest(
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        connect_timeout=30,
        pool_timeout=30
    )
    
    bot = Bot(
        token=settings.TELEGRAM_FILE_BOT_TOKEN,
        request=request
    )
    
    async def send_with_retry(max_retries=3):
        """Send file with retry logic"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Upload attempt {attempt + 1}/{max_retries}")
                start_time = time.time()
                
                # Reset file position if it's seekable
                if hasattr(file, 'seek'):
                    file.seek(0)
                
                msg = await bot.send_document(
                    chat_id=settings.TELEGRAM_FILE_CHAT_ID,
                    document=file,
                    filename=getattr(file, 'name', 'file'),
                    read_timeout=read_timeout,
                    write_timeout=write_timeout
                )
                
                upload_time = time.time() - start_time
                logger.info(f"Upload successful in {upload_time:.2f} seconds")
                return msg
                
            except Exception as e:
                logger.error(f"Upload attempt {attempt + 1} failed: {e}")
                
                # If it's the last attempt, raise the exception
                if attempt == max_retries - 1:
                    raise e
                    
                # Wait before retrying (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
        
        return None
    
    try:
        msg = asyncio.run(send_with_retry())
    except Exception as e:
        logger.error(f"All upload attempts failed: {e}")
        raise Exception(f"Telegram upload failed after retries: {str(e)}")
    
    if not msg or not getattr(msg, 'document', None):
        raise Exception("Telegram upload failed or returned no document.")
    
    # Create a shorter identifier for the deep link
    short_id = hashlib.md5(msg.document.file_id.encode()).hexdigest()[:12]
    
    # Store the mapping in cache for 24 hours
    cache_key = f"telegram_file_{short_id}"
    cache.set(cache_key, msg.document.file_id, timeout=86400)  # 24 hours
    
    logger.info(f"File uploaded successfully. File ID: {msg.document.file_id}")
    
    return {
        "file_id": msg.document.file_id,
        "download_link": f"https://t.me/{settings.TELEGRAM_FILE_BOT_USERNAME}?start=download_{short_id}",
    }


# Alternative async version if you want to call it from async context
async def upload_to_telegram_async(file):
    """Async version of upload_to_telegram"""
    
    # Get file size for dynamic timeout calculation
    file_size = getattr(file, 'size', 0)
    if hasattr(file, 'seek') and hasattr(file, 'tell'):
        current_pos = file.tell()
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(current_pos)
    
    # Calculate dynamic timeouts
    base_timeout = 60
    size_in_mb = file_size / (1024 * 1024)
    dynamic_timeout = base_timeout + (size_in_mb * 30)
    read_timeout = min(max(dynamic_timeout, 60), 600)
    write_timeout = min(max(dynamic_timeout, 60), 600)
    
    logger.info(f"File size: {file_size} bytes ({size_in_mb:.2f} MB)")
    logger.info(f"Using timeouts: read={read_timeout}s, write={write_timeout}s")
    
    request = HTTPXRequest(
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        connect_timeout=30,
        pool_timeout=30
    )
    
    bot = Bot(
        token=settings.TELEGRAM_FILE_BOT_TOKEN,
        request=request
    )
    
    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Upload attempt {attempt + 1}/{max_retries}")
            start_time = time.time()
            
            if hasattr(file, 'seek'):
                file.seek(0)
            
            msg = await bot.send_document(
                chat_id=settings.TELEGRAM_FILE_CHAT_ID,
                document=file,
                filename=getattr(file, 'name', 'file'),
                read_timeout=read_timeout,
                write_timeout=write_timeout
            )
            
            upload_time = time.time() - start_time
            logger.info(f"Upload successful in {upload_time:.2f} seconds")
            break
            
        except Exception as e:
            logger.error(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise Exception(f"Telegram upload failed after {max_retries} attempts: {str(e)}")
            
            wait_time = 2 ** attempt
            logger.info(f"Waiting {wait_time} seconds before retry...")
            await asyncio.sleep(wait_time)
    
    if not msg or not getattr(msg, 'document', None):
        raise Exception("Telegram upload failed or returned no document.")
    
    # Create short ID and cache
    short_id = hashlib.md5(msg.document.file_id.encode()).hexdigest()[:12]
    cache_key = f"telegram_file_{short_id}"
    cache.set(cache_key, msg.document.file_id, timeout=86400)
    
    logger.info(f"File uploaded successfully. File ID: {msg.document.file_id}")
    
    return {
        "file_id": msg.document.file_id,
        "download_link": f"https://t.me/{settings.TELEGRAM_FILE_BOT_USERNAME}?start=download_{short_id}",
    }