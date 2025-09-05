from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Course, Enrollment, Wishlist, ScheduleSlot
from .cache_keys import COURSES_LIST_KEY
from reports.models import Report
from reports.tasks import generate_student_performance_report
import django_rq

def _bust_courses_cache(sender, **kwargs):
    from django.core.cache import cache
    # Flush every language variant (cheap with Redis)
    cache.delete_pattern(COURSES_LIST_KEY.replace('{lang}', '*'))

for model in (Course, Wishlist, ScheduleSlot):
    post_save.connect(_bust_courses_cache, sender=model)
    post_delete.connect(_bust_courses_cache, sender=model)
    
    
    
    
    
@receiver(post_save, sender=Enrollment)
def trigger_student_performance_report(sender, instance, **kwargs):
    update_fields = kwargs.get('update_fields') or set()
    if instance.status == 'completed' and ('status' in update_fields or kwargs.get('created', False)):
        if not Report.objects.filter(report_type='student_performance', parameters__enrollment_id=instance.id).exists():
            report = Report.objects.create(
                report_type='student_performance',
                requested_by=instance.student,
                status='pending',
                parameters={'enrollment_id': instance.id}
            )
            queue = django_rq.get_queue('default')
            job = queue.enqueue(generate_student_performance_report, report.id, instance.id)
            report.job_id = job.id
            report.save()