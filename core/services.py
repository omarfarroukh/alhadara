from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()

def send_notification(recipient_id, notification_type, title, message, data=None):
    """Create notification and send via WebSocket"""
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
    
    return notification

def notify_deposit_request_created(deposit_request):
    """Notify reception and admin about new deposit request"""
    # Get all reception and admin users
    staff_users = User.objects.filter(
        user_type__in=['reception', 'admin']
    ).values_list('id', flat=True)
    
    for user_id in staff_users:
        send_notification(
            recipient_id=user_id,
            notification_type='deposit_request',
            title='New Deposit Request',
            message=f'New deposit request for {deposit_request.amount} from {deposit_request.user.get_full_name()}',
            data={'deposit_request_id': deposit_request.id}
        )

def notify_deposit_status_changed(deposit_request, status):
    """Notify user about deposit request status change"""
    status_text = 'approved' if status == 'verified' else 'rejected'
    
    send_notification(
        recipient_id=deposit_request.user.id,
        notification_type=f'deposit_{status_text}',
        title=f'Deposit Request {status_text.title()}',
        message=f'Your deposit request for {deposit_request.amount} has been {status_text}.',
        data={'deposit_request_id': deposit_request.id, 'status': status}
    ) 