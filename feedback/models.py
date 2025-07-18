from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.

class Feedback(models.Model):
    scheduleslot = models.ForeignKey('courses.ScheduleSlot', on_delete=models.CASCADE, related_name='feedbacks')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks')
    teacher_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    material_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    facilities_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    app_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('scheduleslot', 'student')

    @property
    def total_rating(self):
        return round((self.teacher_rating + self.material_rating + self.facilities_rating + self.app_rating) / 4, 2)

    def __str__(self):
        return f"Feedback for {self.scheduleslot} by {self.student} (Total: {self.total_rating})"
