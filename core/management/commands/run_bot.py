# core/management/commands/run_bot.py
import asyncio
import nest_asyncio  # Critical for Django + async
from django.core.management.base import BaseCommand
from core.bots.telegram_bot import setup_bot

nest_asyncio.apply()  # Fix event loop conflicts

class Command(BaseCommand):
    help = "Starts the Telegram bot"

    def handle(self, *args, **options):
        asyncio.run(self._run_bot())

    async def _run_bot(self):
        try:
            application = setup_bot()
            await application.initialize()  # Explicit initialization
            self.stdout.write(self.style.SUCCESS("Bot started successfully!"))
            await application.run_polling()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Bot failed: {str(e)}"))