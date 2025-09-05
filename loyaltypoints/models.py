# loyaltypoints/models.py
from django.db import models
from django.conf import settings

class LoyaltyPoint(models.Model):
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_points')
    points = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.points} points"

class LoyaltyPointLog(models.Model):
    """A simple log for all loyalty point movements. No pending state."""
    loyalty_account = models.ForeignKey(LoyaltyPoint, on_delete=models.CASCADE, related_name='logs')
    # Positive for awards, negative for deductions/spending
    points = models.IntegerField()
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.loyalty_account.student}: {self.points} points for {self.reason}"

    class Meta:
        ordering = ['-created_at']