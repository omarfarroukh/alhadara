# reports/models.py
from django.db import models
from django.conf import settings
from core.models import FileStorage

class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        # Admin - Financial
        ('financial_summary_period', 'Financial Summary (Time Period)'),
        # Admin - Statistical
        ('statistical_summary_period', 'Statistical Summary (Time Period)'),
        # Admin - Qualitative
        ('feedback_summary', 'Feedback Summary (Time Period)'),
        ('complaints_summary', 'Complaints Summary (Time Period)'),
        # Admin - Academic
        ('schedule_slot_performance', 'Schedule Slot Performance'),
        # Student
        ('student_performance', 'Student Performance Summary'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    file_storage = models.OneToOneField(FileStorage, on_delete=models.SET_NULL, null=True, blank=True)
    
    job_id = models.CharField(max_length=255, blank=True, null=True, help_text="RQ Job ID")
    error_message = models.TextField(blank=True, null=True)

    parameters = models.JSONField(default=dict, blank=True, help_text="Parameters used for the report, e.g., dates")

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_report_type_display()} for {self.requested_by}"

    class Meta:
        ordering = ['-created_at']