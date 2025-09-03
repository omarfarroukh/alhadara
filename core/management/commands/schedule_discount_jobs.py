from django.core.management.base import BaseCommand
from django_rq import get_scheduler
from django.utils import timezone
from courses.models import CourseDiscount
from courses.tasks import apply_course_discount, remove_course_discount, cancel_scheduled_job

JOB_ID = "discount-maintenance-cron"
DEFAULT_CRON = "* * * * *"          # every minute for testing


# ---- module-level helper (pickle-safe) -----------------------------
def _discount_maintenance():
    """Ensure every active discount has its activation/expiration jobs."""
    now = timezone.now()
    qs = CourseDiscount.objects.filter(status='active', end_date__gt=now)
    scheduler = get_scheduler('default')

    for disc in qs:
        if disc.start_date > now and not disc.activation_job_id:
            job = scheduler.enqueue_at(
                disc.start_date,
                apply_course_discount,
                disc.id
            )
            CourseDiscount.objects.filter(pk=disc.pk).update(
                activation_job_id=job.id
            )

        if not disc.expiration_job_id:
            job = scheduler.enqueue_at(
                disc.end_date,
                remove_course_discount,
                disc.id
            )
            CourseDiscount.objects.filter(pk=disc.pk).update(
                expiration_job_id=job.id
            )


# ---- command -------------------------------------------------------
class Command(BaseCommand):
    help = "Register/show/delete a 1-minute cron job that queues discount tasks."

    def add_arguments(self, parser):
        parser.add_argument("--cron", metavar='"*/5 * * * *"', help="Cron string")
        parser.add_argument("--show", action="store_true")
        parser.add_argument("--delete", action="store_true")

    def handle(self, *args, **opts):
        scheduler = get_scheduler('default')

        if opts["show"]:
            job = next((j for j in scheduler.get_jobs() if j.id == JOB_ID), None)
            self.stdout.write(
                self.style.SUCCESS(f"Job scheduled: {job}") if job else "No job."
            )
            return

        if opts["delete"]:
            job = next((j for j in scheduler.get_jobs() if j.id == JOB_ID), None)
            if job:
                scheduler.cancel(job)
                self.stdout.write(self.style.SUCCESS("Cancelled."))
            return

        # (re-)register
        cron = opts["cron"] or DEFAULT_CRON
        scheduler.cron(
            cron,
            func=_discount_maintenance,   # plain function, no stdout objects
            id=JOB_ID,
            queue_name="default",
            repeat=None,
            timeout=120,
            meta={"cron_string": cron},
        )
        self.stdout.write(
            self.style.SUCCESS(f"Registered cron '{cron}' with id '{JOB_ID}'")
        )