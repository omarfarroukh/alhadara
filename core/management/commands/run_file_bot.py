from django.core.management.base import BaseCommand
from core.bots.file_storage_bot import start_bot

class Command(BaseCommand):
    help = "Runs the Telegram file storage bot"

    def handle(self, *args, **options):
        start_bot()  # Now handles async internally