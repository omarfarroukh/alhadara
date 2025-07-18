from django.db import models
from django.conf import settings

class LoyaltyPoint(models.Model):
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_points')
    points = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.points} points"

    def transform_to_ewallet(self, amount, reason="Transformed to ewallet"):
        if self.points < amount:
            raise ValueError("Not enough points")
        self.points -= amount
        # Assume student has 'ewallet_balance' field
        self.student.ewallet_balance = getattr(self.student, 'ewallet_balance', 0) + amount
        self.student.save()
        self.save()
        LoyaltyPointAudit.objects.create(
            student=self.student,
            change=-amount,
            reason=reason,
            balance_after=self.points
        )

