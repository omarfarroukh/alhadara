from django.core.management.base import BaseCommand
from core.tasks import update_enrollment_statuses_bulk
from django_rq.queues import get_scheduler

class Command(BaseCommand):
    help = 'Schedule the RQ job to update all enrollments statuses twice daily (00:00 and 12:00), or run immediately with --now.'

    def add_arguments(self, parser):
        parser.add_argument('--now', action='store_true', help='Run the update_enrollment_statuses_bulk job immediately')

    def handle(self, *args, **options):
        if options['now']:
            print('Running update_enrollment_statuses_bulk job immediately...')
            update_enrollment_statuses_bulk.delay()
            print('Job enqueued.')
            return
        scheduler = get_scheduler('default')
        job_func = 'core.tasks.update_enrollment_statuses_bulk'
        # Remove existing jobs for this function to avoid duplicates
        for job in scheduler.get_jobs():
            func_name = getattr(job, 'func_name', None) or getattr(job, 'func', None)
            if func_name == job_func:
                scheduler.cancel(job)
        # Schedule at 00:00 and 12:00 every day
        for hour in [0, 12]:
            scheduler.cron(
                "0 {} * * *".format(hour),
                job_func,
                repeat=None,
                queue_name='default',
            )
        print('Scheduled update_enrollment_statuses_bulk RQ job for 00:00 and 12:00 daily.') 