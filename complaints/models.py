from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from courses.models import Enrollment 
User = get_user_model()

class Complaint(models.Model):
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    )
    
    TYPE_CHOICES = (
        ('general', 'General Complaint'),
        ('course', 'About a Course'),
        ('teacher', 'About a Teacher'),
        ('facility', 'About Facility/Hall'),
        ('other', 'Other'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='complaints',
        limit_choices_to={'user_type': 'student'}
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Reference to enrollment instead of schedule_slot
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints'
    )
    
    # Management fields
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints',
        limit_choices_to={'is_staff': True}
    )
    resolution_notes = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('can_resolve_complaint', 'Can resolve complaints'),
        ]
    
    def __str__(self):
        return f"Complaint #{self.id}: {self.title} ({self.get_status_display()})"
    
    def clean(self):
        """Validate that enrollment matches the student when provided"""
        super().clean()
        
        if self.enrollment and self.enrollment.student != self.student:
            raise ValidationError("Enrollment does not belong to the complaining student")
    
    def save(self, *args, **kwargs):
        """Update timestamps when resolving"""
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def schedule_slot(self):
        """Access schedule_slot through enrollment if available"""
        return self.enrollment.schedule_slot if self.enrollment else None