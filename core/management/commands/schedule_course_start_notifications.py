# core/management/commands/schedule_course_start_notifications.py
from django.core.management.base import BaseCommand
from django_rq import get_scheduler
from core.tasks import send_course_reminders_task

JOB_ID = "daily-course-start-notify"      # one canonical id
DEFAULT_CRON = "0 0 * * *"               # midnight UTC

class Command(BaseCommand):
    help = (
        "Register, update, show, or delete the cron schedule for "
        "`send_course_start_notifications_task` in rq‑scheduler."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cron",
            metavar='"0 7 * * *"',
            help=f'New cron schedule (default {DEFAULT_CRON}).',
        )
        parser.add_argument(
            "--show",
            action="store_true",
            help="Display the current schedule and exit."
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the scheduled job."
        )

    def handle(self, *args, **opts):
        scheduler = get_scheduler("default")

        # helper – find existing job (if any)
        job = next((j for j in scheduler.get_jobs() if j.id == JOB_ID), None)

        # ---- show ------------------------------------------------------
        if opts["show"]:
            if job:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Job '{JOB_ID}' is scheduled as cron “{job.meta['cron_string']}”"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("Job not found"))
            return

        # ---- delete ----------------------------------------------------
        if opts["delete"]:
            if job:
                scheduler.cancel(job)
                self.stdout.write(self.style.SUCCESS(f"Deleted job '{JOB_ID}'"))
            else:
                self.stdout.write(self.style.WARNING("Nothing to delete – job not found"))
            return

        # ---- create / update ------------------------------------------
        cron = opts["cron"] or DEFAULT_CRON

        # If job exists, replace it
        if job:
            scheduler.cancel(job)

        scheduler.cron(
            cron,
            func=send_course_reminders_task,
            id=JOB_ID,
            queue_name="default",
            repeat=None,          # infinite
            timeout=600,
            result_ttl=24 * 3600, # keep result 1 day
            meta={"cron_string": cron},
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Job '{JOB_ID}' registered with cron “{cron}”"
            )
        )
