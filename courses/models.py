from django.db import models
from core.models import Interest, StudyField
from django.db.models import Q
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    
    def __str__(self):
        return f"{self.name}"
    class Meta:
        ordering = ['name']  


class CourseType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='course_types')
    
    def __str__(self):
        return f"{self.name}"
class CourseTypeTag(models.Model):
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='tags')
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE, null=True, blank=True)
    study_field = models.ForeignKey(StudyField, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('course_type', 'interest', 'study_field')

    def __str__(self):
        return f"{self.course_type.name} - {self.interest or self.study_field}"

class Hall(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    location = models.CharField(max_length=255)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Must be at least 0.01"
    )
    
    def __str__(self):
        return f"{self.name} ({self.location})"
    
    def clean(self):
        """Add any complex validation here"""
        super().clean()
        if self.hourly_rate <= 0:
            raise ValidationError("Hourly rate must be positive")
        if self.capacity <= 0:
            raise ValidationError("Capacity must be positive")


class Course(models.Model):
    CATEGORY_CHOICES = (
        ('course', 'course'),
        ('workshop', 'Workshop')
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Must be at least 0.01"
    )
    duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration in hours (must be at least 1)"
    )
    max_students = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    certification_eligible = models.BooleanField(default=False)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='courses')
    
    def __str__(self):
        return self.title
        
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'department'],
                name='unique_course_title_per_department'
            )
        ]
        
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        if self.duration < 1:
            raise ValidationError("Duration must be at least 1 hour")
            
        if self.price <= 0:
            raise ValidationError("Price must be positive")
            
        if self.max_students <= 0:
            raise ValidationError('Max students must be positive')
            
        if self.course_type.department != self.department:
            raise ValidationError(
                "The selected course type does not belong to the specified department"
            )
    
class ScheduleSlot(models.Model):
    DAY_CHOICES = (
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday')
    )
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='schedule_slots')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='schedule_slots')
    teacher = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='teaching_slots',
        limit_choices_to={'user_type': 'teacher'}
    )
    days_of_week = models.JSONField(default=list)
    start_time = models.TimeField()
    end_time = models.TimeField()
    recurring = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    
    def __str__(self):
        days = ", ".join([self.get_day_display(day) for day in self.days_of_week])
        teacher_name = self.teacher.get_full_name() if self.teacher else "No teacher"
        return f"{self.course.title} - {teacher_name} - {days} ({self.start_time}-{self.end_time})"
    
    def get_day_display(self, day_code):
        return dict(self.DAY_CHOICES).get(day_code, day_code)
        
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gte=models.F('valid_from')) | 
                     models.Q(valid_until__isnull=True),
                name='valid_until_after_valid_from'
            )
        ]
        
    def clean(self):
        """Model-level validation that works with Django admin"""
        super().clean()
        
        # Basic validations
        if self.valid_from and self.valid_from < date.today() and not self.pk:
            raise ValidationError("Cannot schedule in the past")
            
        if self.valid_until and self.valid_from and self.valid_until < self.valid_from:
            raise ValidationError("End date must be after start date")
            
        if self.recurring and not self.valid_until:
            raise ValidationError("Recurring slots require an end date")
            
        if not self.recurring and self.days_of_week and len(self.days_of_week) > 1:
            raise ValidationError("Non-recurring slots can only have one day specified")

        # Duration validation
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError("End time must be after start time")
                
            duration = (self.end_time.hour - self.start_time.hour) + \
                      (self.end_time.minute - self.start_time.minute)/60
            if duration > 8:
                raise ValidationError("Time slots cannot exceed 8 hours")
            if duration < 0.5:
                raise ValidationError("Time slots must be at least 30 minutes")

        # Course capacity vs hall capacity
        if self.course and self.hall and self.course.max_students > self.hall.capacity:
            raise ValidationError(
                f"Course capacity ({self.course.max_students}) "
                f"exceeds hall capacity ({self.hall.capacity})"
            )

        # Date range validation
        if self.valid_from and self.valid_until and (self.valid_until - self.valid_from).days > 365:
            raise ValidationError("Schedule slots cannot span more than 1 year")

        # Hall overlap detection
        if self.hall and self.days_of_week and self.start_time and self.end_time:
            self._check_hall_availability()

        # Teacher availability check
        if self.teacher and self.days_of_week and self.start_time and self.end_time:
            self._check_teacher_availability()

    def _check_hall_availability(self):
        """Check if hall is already booked for the given time slot"""
        # Build day overlap condition
        day_overlap_condition = Q()
        for day in self.days_of_week:
            day_overlap_condition |= Q(days_of_week__contains=[day])
        
        overlap_qs = ScheduleSlot.objects.filter(
            hall=self.hall,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).filter(day_overlap_condition)
        
        # Date range filtering
        if self.valid_from and self.valid_until:
            overlap_qs = overlap_qs.filter(
                Q(
                    Q(valid_until__isnull=True) & Q(valid_from__lte=self.valid_until)
                ) | Q(
                    Q(valid_until__isnull=False) & 
                    Q(valid_from__lte=self.valid_until) & 
                    Q(valid_until__gte=self.valid_from)
                )
            )
        elif self.valid_from:
            overlap_qs = overlap_qs.filter(
                Q(valid_until__gte=self.valid_from) | Q(valid_until__isnull=True)
            )
        
        # Exclude current instance when updating
        if self.pk:
            overlap_qs = overlap_qs.exclude(pk=self.pk)
        
        if overlap_qs.exists():
            conflicting_slot = overlap_qs.first()
            raise ValidationError(
                f"Hall '{self.hall.name}' is already booked for "
                f"{conflicting_slot.course.title} on {', '.join(conflicting_slot.days_of_week)} "
                f"from {conflicting_slot.start_time} to {conflicting_slot.end_time}"
            )

    def _check_teacher_availability(self):
        """Check if teacher is already booked for the given time slot"""
        # Build day overlap condition
        day_overlap_condition = Q()
        for day in self.days_of_week:
            day_overlap_condition |= Q(days_of_week__contains=[day])
        
        overlap_qs = ScheduleSlot.objects.filter(
            teacher=self.teacher,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).filter(day_overlap_condition)
        
        # Date range filtering
        if self.valid_from and self.valid_until:
            overlap_qs = overlap_qs.filter(
                Q(
                    Q(valid_until__isnull=True) & Q(valid_from__lte=self.valid_until)
                ) | Q(
                    Q(valid_until__isnull=False) & 
                    Q(valid_from__lte=self.valid_until) & 
                    Q(valid_until__gte=self.valid_from)
                )
            )
        elif self.valid_from:
            overlap_qs = overlap_qs.filter(
                Q(valid_until__gte=self.valid_from) | Q(valid_until__isnull=True)
            )
        
        # Exclude current instance when updating
        if self.pk:
            overlap_qs = overlap_qs.exclude(pk=self.pk)
        
        if overlap_qs.exists():
            conflicting_slot = overlap_qs.first()
            raise ValidationError(
                f"Teacher '{self.teacher.get_full_name()}' is already scheduled for "
                f"{conflicting_slot.course.title} on {', '.join(conflicting_slot.days_of_week)} "
                f"from {conflicting_slot.start_time} to {conflicting_slot.end_time}"
            )

class Booking(models.Model):
    PURPOSE_CHOICES = (
        ('course', 'Course'),
        ('tutoring', 'Tutoring'),
        ('meeting', 'Meeting'),
        ('event', 'Event'),
        ('other', 'Other')
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled')
    )
    
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='bookings')
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings_requested')
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='bookings_as_student', limit_choices_to={'user_type': 'student'})
    tutor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='bookings_as_tutor', limit_choices_to={'user_type': 'teacher'})
    # Guest information fields
    guest_name = models.CharField(max_length=255, null=True, blank=True)
    guest_email = models.EmailField(null=True, blank=True)
    guest_phone = models.CharField(max_length=20, null=True, blank=True)
    guest_organization = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_purpose_display()} - {self.hall.name} ({self.start_datetime})"
    
    class Meta:
        ordering = ['-start_datetime']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_datetime__lt=models.F('end_datetime')),
                name='booking_start_before_end'
            ),
        ]