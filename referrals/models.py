from django.db import models
from django.conf import settings

# Create your models here.

class ReferralCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_code')
    code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.code}"

class ReferralUsage(models.Model):
    code = models.ForeignKey(ReferralCode, on_delete=models.CASCADE, related_name='usages')
    used_by = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='used_referral')
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.used_by} used {self.code.code}"
