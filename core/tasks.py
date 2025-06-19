from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from .models import Notification
from courses.models import Enrollment
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@shared_task
def send_notification_task(recipient_id, notification_type, title, message, data=None):
    """Celery task to send notification"""
    try:
        # Create notification in database
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data=data or {}
        )
        
        # Send via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{recipient_id}",
            {
                "type": "notification.message",
                "notification": {
                    "id": notification.id,
                    "type": notification.notification_type,
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data,
                    "created_at": notification.created_at.isoformat(),
                }
            }
        )
        
        return f"Notification sent to user {recipient_id}"
    except Exception as e:
        # Log error and retry
        raise self.retry(exc=e, countdown=60, max_retries=3)

@shared_task
def send_deposit_notification_task(deposit_request_id, notification_type):
    """Send deposit-related notifications"""
    from .models import DepositRequest
    
    try:
        deposit_request = DepositRequest.objects.get(id=deposit_request_id)
        
        if notification_type == 'created':
            # Notify admin and reception
            staff_users = User.objects.filter(
                user_type__in=['reception', 'admin']
            ).values_list('id', flat=True)
            
            for user_id in staff_users:
                send_notification_task.delay(
                    recipient_id=user_id,
                    notification_type='deposit_request',
                    title='New Deposit Request',
                    message=f'New deposit request for {deposit_request.amount} from {deposit_request.user.get_full_name()}',
                    data={'deposit_request_id': deposit_request.id}
                )
        
        elif notification_type in ['approved', 'rejected']:
            status_text = 'approved' if notification_type == 'approved' else 'rejected'
            send_notification_task.delay(
                recipient_id=deposit_request.user.id,
                notification_type=f'deposit_{status_text}',
                title=f'Deposit Request {status_text.title()}',
                message=f'Your deposit request for {deposit_request.amount} has been {status_text}.',
                data={'deposit_request_id': deposit_request.id, 'status': notification_type}
            )
            
    except DepositRequest.DoesNotExist:
        pass

@shared_task
def send_course_enrollment_notification_task(enrollment_id):
    """Send course enrollment notification"""
    try:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        
        # Notify admin and reception
        staff_users = User.objects.filter(
            user_type__in=['reception', 'admin']
        ).values_list('id', flat=True)
        
        for user_id in staff_users:
            send_notification_task.delay(
                recipient_id=user_id,
                notification_type='course_enrollment',
                title='New Course Enrollment',
                message=f'{enrollment.student.get_full_name()} enrolled in {enrollment.course.title}',
                data={
                    'enrollment_id': enrollment.id,
                    'student_id': enrollment.student.id,
                    'course_id': enrollment.course.id
                }
            )
    except Enrollment.DoesNotExist:
        pass

@shared_task
def send_course_payment_notification_task(enrollment_id, amount):
    """Send course payment notification"""
    try:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        
        # Notify admin and reception
        staff_users = User.objects.filter(
            user_type__in=['reception', 'admin']
        ).values_list('id', flat=True)
        
        for user_id in staff_users:
            send_notification_task.delay(
                recipient_id=user_id,
                notification_type='course_payment',
                title='Course Payment Received',
                message=f'{enrollment.student.get_full_name()} made a payment of {amount} for {enrollment.course.title}',
                data={
                    'enrollment_id': enrollment.id,
                    'student_id': enrollment.student.id,
                    'course_id': enrollment.course.id,
                    'amount': str(amount)
                }
            )
    except Enrollment.DoesNotExist:
        pass

@shared_task
def send_course_start_notifications_task():
    """Scheduled task to send course start notifications"""
    today = timezone.now().date()
    
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
                send_notification_task.delay(
                    recipient_id=enrollment.student.id,
                    notification_type='course_starting',
                    title='Course Starting Today',
                    message=f'Your course "{enrollment.course.title}" starts today!',
                    data={
                        'enrollment_id': enrollment.id,
                        'course_id': enrollment.course.id,
                        'course_title': enrollment.course.title
                    }
                )
                notifications_sent += 1
            
            # Course starting in 3 days
            elif days_until_start == 3:
                send_notification_task.delay(
                    recipient_id=enrollment.student.id,
                    notification_type='course_starting_soon',
                    title='Course Starting in 3 Days',
                    message=f'Your course "{enrollment.course.title}" starts in 3 days.',
                    data={
                        'enrollment_id': enrollment.id,
                        'course_id': enrollment.course.id,
                        'course_title': enrollment.course.title,
                        'days_until_start': 3
                    }
                )
                notifications_sent += 1
            
            # Course starting in 1 day
            elif days_until_start == 1:
                send_notification_task.delay(
                    recipient_id=enrollment.student.id,
                    notification_type='course_starting_soon',
                    title='Course Starting Tomorrow',
                    message=f'Your course "{enrollment.course.title}" starts tomorrow.',
                    data={
                        'enrollment_id': enrollment.id,
                        'course_id': enrollment.course.id,
                        'course_title': enrollment.course.title,
                        'days_until_start': 1
                    }
                )
                notifications_sent += 1
    
    return f"Sent {notifications_sent} course start notifications" 