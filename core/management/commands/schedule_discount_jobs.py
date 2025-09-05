from django.core.management.base import BaseCommand
from django_rq import get_scheduler
from django.utils import timezone

from courses.models import CourseDiscount
# Import the specific tasks this maintenance job will schedule
from courses.tasks import apply_course_discount, remove_course_discount

JOB_ID = "discount-maintenance-cron"
# Run every 5 minutes. This is frequent enough to catch missed jobs quickly.
DEFAULT_CRON = "*/5 * * * *"

# This is a module-level function, which is required for RQ to pickle it correctly.
# Do NOT place this inside the Command class.
def _discount_maintenance_job():
    """
    Self-healing task. Scans active discounts and ensures their individual
    activation/expiration jobs are properly scheduled in RQ.
    """
    now = timezone.now()
    # Find all discounts that should be active now or in the future
    active_discounts = CourseDiscount.objects.filter(status='active', end_date__gt=now)
    scheduler = get_scheduler('default')

    for disc in active_discounts:
        # Check 1: Does it need an activation job?
        # This is for discounts starting in the future that might have lost their job.
        if disc.start_date > now and not scheduler.fetch_job(str(disc.activation_job_id)):
            job = scheduler.enqueue_at(
                disc.start_date,
                apply_course_discount,
                disc.id
            )
            # Update the model with the new job ID
            CourseDiscount.objects.filter(pk=disc.pk).update(activation_job_id=job.id)
            print(f"Re-scheduled activation for discount {disc.id}")

        # Check 2: Does it need an expiration job?
        # This is a critical check for any active discount.
        if not scheduler.fetch_job(str(disc.expiration_job_id)):
            job = scheduler.enqueue_at(
                disc.end_date,
                remove_course_discount,
                disc.id
            )
            # Update the model with the new job ID
            CourseDiscount.objects.filter(pk=disc.pk).update(expiration_job_id=job.id)
            print(f"Re-scheduled expiration for discount {disc.id}")
    
    return f"Checked {active_discounts.count()} active discounts."


class Command(BaseCommand):
    help = f"Registers the self-healing discount maintenance job with RQ Scheduler. Cron: '{DEFAULT_CRON}'"

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
            func=_discount_maintenance_job,
            id=JOB_ID,
            queue_name="default",
            timeout=300,  # 5 minutes
            meta={"cron_string": cron_string}
        )
        self.stdout.write(self.style.SUCCESS(f"Registered job '{JOB_ID}' with cron string '{cron_string}'"))