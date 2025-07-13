from django.db import models
from courses.models import Course,ScheduleSlot
from django.db.models import Q
from datetime import date, datetime
from django.core.validators import FileExtensionValidator
from django.contrib.auth import get_user_model
import os
import logging
logger = logging.getLogger(__name__)
User = get_user_model()
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary_storage.storage import RawMediaCloudinaryStorage, MediaCloudinaryStorage


# Create your models here.
class Lesson(models.Model):
    """
    Model for lessons within courses
    """
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True, help_text="Lesson notes and content")
    file = models.FileField(
        upload_to='lessons/files/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip'])],
        help_text="Upload lesson materials (PDF, DOC, PPT, etc.)"
    )
    link = models.URLField(blank=True, null=True, help_text="External link for lesson resources")
    
    # Relationships
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons_in_lessons_app')
    schedule_slot = models.ForeignKey(ScheduleSlot, on_delete=models.CASCADE, related_name='lessons_in_lessons_app')
    
    # Metadata
    lesson_order = models.PositiveIntegerField(default=1, help_text="Order of lesson in the course")
    lesson_date = models.DateField(help_text="Date when lesson is scheduled/conducted")
    
    # Status
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['lesson_date', 'lesson_order']
    
    def __str__(self):
        return f"{self.course.title} - Lesson {self.lesson_order}: {self.title}"
    
    @property
    def file_name(self):
        """Get the filename without path"""
        if self.file:
            return os.path.basename(self.file.name)
        return None
    
    @property
    def file_size(self):
        """Get file size in bytes"""
        if self.file:
            return self.file.size
        return None

    @property
    def duration_hours(self):
        """Calculate duration in hours from schedule slot times"""
        if self.schedule_slot and self.schedule_slot.start_time and self.schedule_slot.end_time:
            # Create datetime objects for calculation
            start_dt = datetime.combine(date.today(), self.schedule_slot.start_time)
            end_dt = datetime.combine(date.today(), self.schedule_slot.end_time)
            
            # Calculate duration
            duration = end_dt - start_dt
            return round(duration.total_seconds() / 3600, 2)  # Convert seconds to hours
        return 0.0
    
    @property
    def teacher(self):
        return self.schedule_slot.teacher if self.schedule_slot else None

    @property
    def is_completed(self):
        return self.status == 'completed'

class Homework(models.Model):
    """
    Model for homework assignments for lessons
    """
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Homework description and instructions")
    form_link = models.URLField(
        blank=True, 
        null=True, 
        help_text="Link to Google Form, survey, or submission form"
    )
    deadline = models.DateTimeField(help_text="Homework submission deadline")
    
    # Relationships
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='homework_assignments_in_lessons_app')
    
    # Additional fields
    max_score = models.PositiveIntegerField(default=100, help_text="Maximum possible score")
    is_mandatory = models.BooleanField(default=True, help_text="Whether homework is mandatory")
    
    # Status
    STATUS_CHOICES = [
        ('published', 'Published'),
        ('closed', 'Closed'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='published',  # Change default to published
        editable=False  # Make non-editable through forms/API
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
    
    @property
    def is_overdue(self):
        """Check if homework deadline has passed"""
        from django.utils import timezone
        return timezone.now() > self.deadline
    
    @property
    def days_until_deadline(self):
        """Get days until deadline"""
        from django.utils import timezone
        if self.is_overdue:
            return 0
        delta = self.deadline - timezone.now()
        return delta.days

    @property
    def course(self):
        return self.lesson.course if self.lesson else None

    @property
    def teacher(self):
        return self.lesson.teacher if self.lesson else None

class Attendance(models.Model):
    """
    Model for tracking student attendance in lessons
    """
    ATTENDANCE_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
    ]
    
    # Relationships
    enrollment = models.ForeignKey('courses.Enrollment', on_delete=models.CASCADE, related_name='attendance_records_in_lessons_app', null=True, blank=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='attendance_records_in_lessons_app')
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recorded_attendance_in_lessons_app',
        help_text="Teacher who recorded the attendance"
    )
    
    # Attendance data
    attendance = models.CharField(max_length=20, choices=ATTENDANCE_CHOICES)
    
    # Timestamps
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['enrollment', 'lesson']
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.enrollment} - {self.lesson.title} - {self.get_attendance_display()}"

    @property
    def student_name(self):
        return self.enrollment.student.get_full_name() if self.enrollment and self.enrollment.student else None

    @property
    def lesson_title(self):
        return self.lesson.title if self.lesson else None

class HomeworkGrade(models.Model):
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='grades')
    enrollment = models.ForeignKey('courses.Enrollment', on_delete=models.CASCADE, related_name='homework_grades')
    grade = models.FloatField(null=True, blank=True)
    comment = models.TextField(blank=True, null=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_homeworks')
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('homework', 'enrollment')

    def __str__(self):
        return f"{self.homework} - {self.enrollment}: {self.grade}"

class ScheduleSlotNews(models.Model):
    TYPE_CHOICES = [
        ('homework', 'Homework'),
        ('quiz', 'Quiz'),
        ('message', 'Message'),
        ('file', 'File'),
        ('image', 'Image'),
    ]
    schedule_slot = models.ForeignKey('courses.ScheduleSlot', on_delete=models.CASCADE, related_name='news')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='news/files/', blank=True, null=True)
    image = models.ImageField(upload_to='news/images/', blank=True, null=True)
    related_homework = models.ForeignKey('lessons.Homework', on_delete=models.SET_NULL, null=True, blank=True)
    related_quiz = models.ForeignKey('quiz.Quiz', on_delete=models.SET_NULL, null=True, blank=True)
    file_storage = models.ForeignKey('core.FileStorage', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.schedule_slot} - {self.type} - {self.title}"

class PrivateLessonRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('proposed', 'Proposed Alternatives'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_lesson_requests')
    schedule_slot = models.ForeignKey('courses.ScheduleSlot', on_delete=models.CASCADE, related_name='private_lesson_requests')
    preferred_date = models.DateField()
    preferred_time_from = models.TimeField()
    preferred_time_to = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    confirmed_date = models.DateField(null=True, blank=True)
    confirmed_time_from = models.TimeField(null=True, blank=True)
    confirmed_time_to = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} - {self.schedule_slot} ({self.status})"

class PrivateLessonProposedOption(models.Model):
    request = models.ForeignKey(PrivateLessonRequest, on_delete=models.CASCADE, related_name='proposed_options')
    date = models.DateField()
    time_from = models.TimeField()
    time_to = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Option for {self.request} on {self.date} {self.time_from}-{self.time_to}"
