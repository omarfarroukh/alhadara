from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, EWallet, Transaction
from .tasks import notify_ewallet_transfer_task


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