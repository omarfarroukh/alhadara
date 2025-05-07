from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Profile, EWallet


@receiver(post_save, sender=User)
def create_user_profile_and_wallet(sender, instance, created, **kwargs):
    """
    Create a profile and wallet for each new user.
    """
    if created:
        # Create an empty profile for the new user
        # The admin or user will need to complete the profile later
        Profile.objects.create(
            user=instance,
            full_name=instance.username,  # Default value, should be updated later
            birth_date='2000-01-01',  # Default value, should be updated later
            gender='other',  # Default value, should be updated later
            national_id='',  # Should be updated later
            address=''  # Should be updated later
        )
        
        # Create an empty wallet for the new user
        EWallet.objects.create(user=instance)