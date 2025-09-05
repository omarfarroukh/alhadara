from django.core.management.base import BaseCommand
from django_rq import get_scheduler
# Import the correct notification task
from core.tasks import notify_course_discounts

JOB_ID = "course-discount-notifier-cron"
# A good default is to run this once a day in the morning.
DEFAULT_CRON = "5 7 * * *"  # 7:05 AM Daily

class Command(BaseCommand):
    help = f"Registers the daily job to notify users of new discounts on their wishlist items. Cron: '{DEFAULT_CRON}'"

    def add_arguments(self, parser):
        parser.add_argument("--cron", default=DEFAULT_CRON, help=f"Custom cron string. Defaults to '{DEFAULT_CRON}'")
        parser.add_argument("--show", action="store_true", help="Show the current status of the job.")
        parser.add_argument("--delete", action="store_true", help="Delete the job from the scheduler.")

    def handle(self, *args, **opts):
        scheduler = get_scheduler('default')
        job = next((j for j in scheduler.get_jobs() if j.id == JOB_ID), None)

        if opts["show"]:
            if job:
                self.stdout.write(self.style.SUCCESS(f"Job found: {job}"))
                self.stdout.write(self.style.SUCCESS(f"  - Cron: {job.meta.get('cron_string')}"))
                self.stdout.write(self.style.SUCCESS(f"  - Next Run: {job.scheduled_for}"))
            else:
                self.stdout.write("No job found with this ID.")
            return

        if opts["delete"]:
            if job:
                scheduler.cancel(job)
                self.stdout.write(self.style.SUCCESS(f"Job '{JOB_ID}' cancelled."))
            else:
                self.stdout.write("No job found to delete.")
            return
        
        if job:
            self.stdout.write(f"Job '{JOB_ID}' already exists. Re-registering to ensure it's up to date.")
            scheduler.cancel(job)

        cron_string = opts["cron"]
        scheduler.cron(
            cron_string,
            func=notify_course_discounts, # <-- The correct task function
            id=JOB_ID,
            queue_name="default",
            timeout=300,  # 5 minutes
            meta={"cron_string": cron_string}
        )
        self.stdout.write(self.style.SUCCESS(f"Registered job '{JOB_ID}' with cron string '{cron_string}'"))