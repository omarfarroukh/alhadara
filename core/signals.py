from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, EWallet

@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Create a wallet for each new user (only if user is newly created)"""
    if created:
        EWallet.objects.create(user=instance)