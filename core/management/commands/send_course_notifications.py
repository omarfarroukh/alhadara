from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from courses.models import Enrollment
from core.services import notify_course_starting, notify_course_starting_soon


class Command(BaseCommand):
    help = 'Send notifications for courses starting soon or starting today'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending notifications',
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        dry_run = options['dry_run']
        
        # Get active enrollments with schedule slots
        enrollments = Enrollment.objects.filter(
            status__in=['pending', 'active'],
            schedule_slot__isnull=False
        ).select_related('student', 'course', 'schedule_slot')
        
        notifications_sent = 0
        
        for enrollment in enrollments:
            schedule_slot = enrollment.schedule_slot
            start_date = schedule_slot.valid_from
            
            if start_date:
                days_until_start = (start_date - today).days
                
                # Course starting today
                if days_until_start == 0:
                    if not dry_run:
                        notify_course_starting(enrollment)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Course starting today: {enrollment.course.title} for {enrollment.student.get_full_name()}'
                        )
                    )
                    notifications_sent += 1
                
                # Course starting in 3 days
                elif days_until_start == 3:
                    if not dry_run:
                        notify_course_starting_soon(enrollment, 3)
                    self.stdout.write(
                        self.style.WARNING(
                            f'Course starting in 3 days: {enrollment.course.title} for {enrollment.student.get_full_name()}'
                        )
                    )
                    notifications_sent += 1
                
                # Course starting in 1 day
                elif days_until_start == 1:
                    if not dry_run:
                        notify_course_starting_soon(enrollment, 1)
                    self.stdout.write(
                        self.style.WARNING(
                            f'Course starting in 1 day: {enrollment.course.title} for {enrollment.student.get_full_name()}'
                        )
                    )
                    notifications_sent += 1
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: Would send {notifications_sent} notifications'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent {notifications_sent} notifications'
                )
            ) 