# complaints/tasks.py
from django_rq import job
from rq import Retry
from .models import Complaint
from core.tasks import send_notification_task
from django.contrib.auth import get_user_model

User = get_user_model()

@job('default', retry=Retry(max=2))
def notify_complaint_created_task(complaint_id):
    """Notifies admin about new complaints"""
    try:
        complaint = Complaint.objects.get(id=complaint_id)
        admin_users = User.objects.filter(
            is_staff=True,
            is_active=True
        ).values_list('id', flat=True)

        for uid in admin_users:
            send_notification_task.delay(
                recipient_id=uid,
                notification_type='new_complaint',
                title='New Complaint Submitted',
                message=f'New complaint from {complaint.student.get_full_name()}: {complaint.title}',
                data={
                    'complaint_id': complaint.id,
                    'type': complaint.type,
                    'priority': complaint.priority
                }
            )
    except Complaint.DoesNotExist:
        pass

@job('default', retry=Retry(max=2))
def notify_complaint_resolved_task(complaint_id):
    """Notifies student when complaint is resolved"""
    try:
        complaint = Complaint.objects.get(id=complaint_id)
        send_notification_task.delay(
            recipient_id=complaint.student.id,
            notification_type='complaint_resolved',
            title='Your Complaint Was Resolved',
            message=f'Your complaint "{complaint.title}" has been resolved',
            data={
                'complaint_id': complaint.id,
                'resolution_notes': complaint.resolution_notes,
                'resolved_at': complaint.resolved_at.isoformat() if complaint.resolved_at else None
            }
        )
    except Complaint.DoesNotExist:
        pass