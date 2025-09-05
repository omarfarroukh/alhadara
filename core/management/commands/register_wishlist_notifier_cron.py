from django.core.management.base import BaseCommand
from django_rq import get_scheduler
from core.tasks import notify_wishlist_slots_available

JOB_ID = "wishlist-slot-notifier-cron"
DEFAULT_CRON = "10 7 * * *"  # 7:10 AM Daily

class Command(BaseCommand):
    help = f"Registers the daily wishlist slot notifier job. Cron: '{DEFAULT_CRON}'"
    # ... (copy the add_arguments and handle methods from the first command) ...
    def add_arguments(self, parser):
        parser.add_argument("--cron", default=DEFAULT_CRON, help=f"Custom cron string. Defaults to '{DEFAULT_CRON}'")
        parser.add_argument("--show", action="store_true", help="Show the current status of the job.")
        parser.add_argument("--delete", action="store_true", help="Delete the job from the scheduler.")

    def handle(self, *args, **opts):
        scheduler = get_scheduler('default')
        job = next((j for j in scheduler.get_jobs() if j.id == JOB_ID), None)

        if opts["show"]:
            if job: self.stdout.write(self.style.SUCCESS(f"Job found: {job}"))
            else: self.stdout.write("No job found with this ID.")
            return

        if opts["delete"]:
            if job:
                scheduler.cancel(job)
                self.stdout.write(self.style.SUCCESS(f"Job '{JOB_ID}' cancelled."))
            else: self.stdout.write("No job found to delete.")
            return
        
        if job:
            self.stdout.write(f"Job '{JOB_ID}' already exists. Re-registering...")
            scheduler.cancel(job)

        cron = opts["cron"]
        scheduler.cron(
            cron,
            func=notify_wishlist_slots_available,
            id=JOB_ID,
            queue_name="default",
            timeout=300
        )
        self.stdout.write(self.style.SUCCESS(f"Registered job '{JOB_ID}' with cron string '{cron}'"))