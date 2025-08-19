from datetime import date, timedelta
from decimal import Decimal
from django_rq import job, get_queue
from rq import Retry
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.utils import timezone
from courses.models import Enrollment
import random
from django.conf import settings
from telegram import Bot
from django.core.cache import cache
from .models import Captcha, Notification, DepositRequest
import logging
import asyncio
User = get_user_model()

# ------------------------- Core Notification Task -----------------------------


logger = logging.getLogger(__name__)


@job('default')
def cleanup_expired_captchas_task():
    cutoff  = timezone.now() - timedelta(minutes=5)
    deleted, _ = Captcha.objects.filter(created_at__lt=cutoff).delete()
    return f"Expired CAPTCHAs removed: {deleted}"



async def _async_send_telegram_message(chat_id, text, parse_mode=None):
    """Asynchronously sends a message to a Telegram chat."""
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode
        )
        logger.info(f"Successfully sent message to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send message to chat_id {chat_id}: {e}")


async def _async_send_pin(chat_id, pin):
    """Sends a verification PIN via Telegram."""
    message = f"🔑 Your verification PIN: **{pin}**\n\nEnter this in the app."
    await _async_send_telegram_message(chat_id, message, parse_mode="Markdown")

def send_telegram_pin(chat_id, token):
    try:
        # Verify token exists
        if not cache.get(f"user_verification:{token}"):
            logger.error(f"Token {token} not found in Redis")
            return

        # Generate and store PIN
        pin = str(random.randint(100000, 999999))
        cache.set(f"verification_pin:{token}", pin, timeout=300)
        logger.info(f"Generated PIN {pin} for token {token}")

        # Run async code in sync context
        asyncio.run(_async_send_pin(chat_id, pin))
        logger.info(f"Sent PIN to chat {chat_id}")

    except Exception as e:
        logger.error(f"Failed to send PIN: {str(e)}")

@job('default',
    timeout=360,
    retry=Retry(max=3, interval=[60, 120, 240]))  # Backoff retry logic
def send_notification_task(recipient_id, notification_type, title, message, data=None):
    """
    Base task: Creates notification and pushes via WebSocket.
    Usage: Always call with .delay() unless in tests/CLI.
    """
    notification = Notification.objects.create(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data or {}
    )

    # WebSocket push
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

# ------------------------- Deposit-Related Tasks ------------------------------

@job('default', retry=Retry(max=2))
def notify_deposit_request_created_task(deposit_request_id):
    """
    Notifies staff about new deposit requests.
    Replaces services.notify_deposit_request_created()
    """
    try:
        deposit_request = DepositRequest.objects.get(id=deposit_request_id)
        staff_ids = User.objects.filter(
            user_type__in=['reception', 'admin']
        ).values_list('id', flat=True)

        for uid in staff_ids:
            send_notification_task.delay(
                recipient_id=uid,
                notification_type='deposit_request',
                title='New Deposit Request',
                message=f'New deposit request for {deposit_request.amount} from {deposit_request.user.get_full_name()}',
                data={'deposit_request_id': deposit_request.id}
            )
    except DepositRequest.DoesNotExist:
        pass

@job('default', retry=Retry(max=2))
def notify_deposit_status_changed_task(deposit_request_id, status):
    """
    Notifies user about deposit approval/rejection.
    Replaces services.notify_deposit_status_changed()
    """
    try:
        deposit_request = DepositRequest.objects.get(id=deposit_request_id)
        status_text = 'approved' if status == 'verified' else 'rejected'
        
        send_notification_task.delay(
            recipient_id=deposit_request.user.id,
            notification_type=f'deposit_{status_text}',
            title=f'Deposit Request {status_text.title()}',
            message=f'Your deposit request for {deposit_request.amount} has been {status_text}.',
            data={
                'deposit_request_id': deposit_request.id,
                'status': status
            }
        )
    except DepositRequest.DoesNotExist:
        pass

# ------------------------- Course-Related Tasks ------------------------------

@job('default')
def notify_course_enrollment_task(enrollment_id):
    """Notifies staff about new course enrollments"""
    try:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        staff_ids = User.objects.filter(
            user_type__in=['reception', 'admin']
        ).values_list('id', flat=True)

        for uid in staff_ids:
            send_notification_task.delay(
                recipient_id=uid,
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

@job('default', retry=Retry(max=2))
def notify_course_cancellation_task(enrollment_id, refund_amount=None, cancelled_by_staff=False):
    """
    Silent handling for guest cancellations:
    - Staff cancelling guest: No notifications
    - Student cancellations: Staff notified
    - Staff cancelling student: Student notified
    """
    try:
        enrollment = Enrollment.objects.select_related('student', 'course').get(id=enrollment_id)
        
        # Silent return for guest cancellations by staff
        if enrollment.is_guest and cancelled_by_staff:
            return "Guest enrollment cancelled silently - no notifications sent"
        
        refund_decimal = Decimal(refund_amount) if refund_amount else None
        
        if cancelled_by_staff:
            # Staff cancelling regular student
            send_notification_task.delay(
                recipient_id=enrollment.student.id,
                notification_type='enrollment_cancelled',
                title='Enrollment Cancelled by Staff',
                message=f"Your enrollment in {enrollment.course.title} was cancelled" +
                    (f" with refund of {refund_decimal}" if refund_decimal else ""),
                data={
                    'enrollment_id': enrollment.id,
                    'course_id': enrollment.course.id,
                    'refund_amount': str(refund_decimal) if refund_decimal else None,
                    'initiated_by': 'staff'
                }
            )
        else:
            # Student self-cancelling (never guests)
            staff_ids = User.objects.filter(
                user_type__in=['reception', 'admin']
            ).values_list('id', flat=True)

            for uid in staff_ids:
                send_notification_task.delay(
                    recipient_id=uid,
                    notification_type='enrollment_cancellation',
                    title='Student Cancelled Enrollment',
                    message=f"{enrollment.student.get_full_name()} cancelled " +
                            f"{enrollment.course.title}" +
                            (f" with refund of {refund_decimal}" if refund_decimal else ""),
                    data={
                        'enrollment_id': enrollment.id,
                        'student_id': enrollment.student.id,
                        'course_id': enrollment.course.id,
                        'refund_amount': str(refund_decimal) if refund_decimal else None,
                        'initiated_by': 'student'
                    }
                )
    
    except Enrollment.DoesNotExist:
        pass
    return "Notifications processed"

@job('default')
def notify_course_payment_task(enrollment_id, amount):
    """Notifies staff about course payments"""
    try:
        enrollment = Enrollment.objects.get(id=enrollment_id)
        staff_ids = User.objects.filter(
            user_type__in=['reception', 'admin']
        ).values_list('id', flat=True)

        for uid in staff_ids:
            send_notification_task.delay(
                recipient_id=uid,
                notification_type='course_payment',
                title='Course Payment Received',
                message=f'{enrollment.student.get_full_name()} paid {amount} for {enrollment.course.title}',
                data={
                    'enrollment_id': enrollment.id,
                    'student_id': enrollment.student.id,
                    'course_id': enrollment.course.id,
                    'amount': str(amount)
                }
            )
    except Enrollment.DoesNotExist:
        pass

# ------------------------- Scheduled Tasks ------------------------------------

@job('default')
def send_course_reminders_task():
    """
    Daily scheduled task for course reminders.
    Sends notifications for courses starting today/tomorrow/in 3 days.
    """
    today = timezone.now().date()
    enrollments = Enrollment.objects.filter(
        status__in=['pending', 'active'],
        schedule_slot__isnull=False
    ).select_related('student', 'course', 'schedule_slot')

    sent = 0
    for enrollment in enrollments:
        days_until = (enrollment.schedule_slot.valid_from - today).days
        if days_until in {0, 1, 2, 3}:
            title = (
                "Course Starting Today" if days_until == 0 else
                "Course Starting Tomorrow" if days_until == 1 else
                "Course Starting in 2 Days" if days_until == 2 else
                "Course Starting in 3 Days"
            )
            
            send_notification_task.delay(
                recipient_id=enrollment.student.id,
                notification_type='course_starting',
                title=title,
                message=f'Your course "{enrollment.course.title}" starts {["today","tomorrow","in 2 days","in 3 days"][days_until]}!',
                data={
                    'enrollment_id': enrollment.id,
                    'course_id': enrollment.course.id,
                    'course_title': enrollment.course.title,
                    'days_until_start': days_until,
                }
            )
            sent += 1
            
    return f"Sent {sent} course reminder notifications"


@job
def update_enrollment_statuses_bulk():
    """Update enrollment statuses using bulk operations"""
    from django.db import transaction
    from datetime import date
    
    today = date.today()
    print(f"Using test date: {today}")
    
    updated_count = 0
    
    with transaction.atomic():
        # Update to pending (courses that haven't started yet)
        pending_count = Enrollment.objects.filter(
            schedule_slot__valid_from__gt=today,
            status__in=['active', 'completed']
        ).exclude(status='cancelled').update(status='pending')
        
        # Update to completed (courses that have ended - using > not >=)
        completed_count = Enrollment.objects.filter(
            schedule_slot__valid_until__lt=today,
            status__in=['pending', 'active']
        ).exclude(status='cancelled').update(status='completed')
        
        # Update to active (courses that are currently running)
        active_count = Enrollment.objects.filter(
            schedule_slot__valid_from__lte=today,
            schedule_slot__valid_until__gte=today,
            status__in=['pending', 'completed']
        ).exclude(status='cancelled').update(status='active')
        
        updated_count = pending_count + completed_count + active_count
    
    print(f"Bulk updated {updated_count} enrollments")
    print(f"  - Pending: {pending_count}")
    print(f"  - Completed: {completed_count}")
    print(f"  - Active: {active_count}")
    return updated_count
# ------------------------- User/Auth-Related Tasks ------------------------------

@job('default', retry=Retry(max=2))
def notify_password_changed_task(user_id):
    """Notifies user about a password change via in-app and Telegram."""
    try:
        user = User.objects.get(id=user_id)
        message = 'Your password has been changed. If you did not initiate this, please contact support immediately.'

        # Send in-app notification
        send_notification_task.delay(
            recipient_id=user.id,
            notification_type='password_changed',
            title='Password Changed Successfully',
            message=message,
            data={'user_id': user.id}
        )

        # Send Telegram notification if chat_id is available
        if user.telegram_chat_id:
            telegram_message = f"Hello {user.get_full_name()},\n\n{message}"
            try:
                asyncio.run(_async_send_telegram_message(user.telegram_chat_id, telegram_message))
                logger.info(f"Sent password change Telegram notification to user {user.id}")
            except Exception as e:
                logger.error(f"Failed to send password change Telegram notification to user {user.id}: {e}")

    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found for password change notification.")
        pass


@job('default', retry=Retry(max=2))
def send_telegram_password_reset_otp_task(user_id, otp):
    """Sends a password reset OTP to the user's Telegram."""
    try:
        user = User.objects.get(id=user_id)
        if user.telegram_chat_id:
            message = f"🔑 Your password reset OTP is: **{otp}**\n\nThis OTP will expire in 10 minutes."
            try:
                asyncio.run(_async_send_telegram_message(user.telegram_chat_id, message, parse_mode="Markdown"))
                logger.info(f"Sent password reset OTP to user {user.id}")
            except Exception as e:
                logger.error(f"Failed to send password reset OTP to user {user.id}: {e}")
        else:
            logger.warning(f"User {user.id} does not have a telegram_chat_id for password reset OTP.")
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} not found for sending password reset OTP.")
        pass

# ------------------------- EWallet-Related Tasks ------------------------------

@job('default', retry=Retry(max=2))
def notify_ewallet_withdrawal_task(user_id, amount):
    """Notifies user about an eWallet withdrawal."""
    try:
        user = User.objects.get(id=user_id)
        send_notification_task.delay(
            recipient_id=user.id,
            notification_type='ewallet_withdrawal',
            title='eWallet Withdrawal',
            message=f'You have successfully withdrawn {amount} from your eWallet.',
            data={'user_id': user.id, 'amount': str(amount)}
        )
    except User.DoesNotExist:
        pass

@job('default', retry=Retry(max=2))
def notify_ewallet_transfer_task(sender_id, receiver_id, amount):
    """Notifies both sender and receiver about an eWallet transfer."""
    try:
        sender = User.objects.get(id=sender_id)
        receiver = User.objects.get(id=receiver_id)

        # Notify sender
        send_notification_task.delay(
            recipient_id=sender.id,
            notification_type='ewallet_transfer_sent',
            title='eWallet Transfer Sent',
            message=f'You have successfully sent {amount} to {receiver.get_full_name()}.',
            data={'sender_id': sender.id, 'receiver_id': receiver.id, 'amount': str(amount)}
        )

        # Notify receiver
        send_notification_task.delay(
            recipient_id=receiver.id,
            notification_type='ewallet_transfer_received',
            title='eWallet Transfer Received',
            message=f'You have received {amount} from {sender.get_full_name()}.',
            data={'sender_id': sender.id, 'receiver_id': receiver.id, 'amount': str(amount)}
        )
    except User.DoesNotExist:
        pass
