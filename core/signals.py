from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Notification, User, EWallet, Transaction
from .tasks import notify_ewallet_transfer_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model


User = get_user_model() 


channel_layer = get_channel_layer()

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Create a wallet for each new user (only if user is newly created)"""
    if created:
        EWallet.objects.create(user=instance)


@receiver(post_save, sender=Transaction)
def notify_on_transfer(sender, instance, created, **kwargs):
    """Send notification when a transfer transaction is created."""
    if created and instance.transaction_type == 'transfer':
        if instance.sender and instance.receiver:
            notify_ewallet_transfer_task.delay(
                sender_id=instance.sender.id,
                receiver_id=instance.receiver.id,
                amount=instance.amount
            )
     
def push_counter_sync(user_id):
    """
    Synchronous version: usable from RQ workers, management commands,
    Django shell, etc.
    """
    User = get_user_model()
    user = User.objects.get(pk=user_id)
    count = user.notifications.filter(is_read=False).count()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {"type": "notification.counter", "unread_count": count}
    )

@receiver([post_save, post_delete], sender=Notification)
def notification_changed(sender, instance, **kwargs):
    push_counter_sync(instance.recipient_id)