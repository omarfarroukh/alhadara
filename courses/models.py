from django.db import models
from core.models import User


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField()
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class CourseType(models.Model):
    CATEGORY_CHOICES = (
        ('core', 'Core'),
        ('elective', 'Elective'),
        ('workshop', 'Workshop')
    )
    
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='course_types')
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.IntegerField(help_text="Duration in hours")
    max_students = models.IntegerField()
    certification_eligible = models.BooleanField(default=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    course_type = models.ForeignKey(CourseType, on_delete=models.CASCADE, related_name='courses')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='taught_courses', limit_choices_to={'user_type': 'teacher'})
    
    def __str__(self):
        return self.title


class Hall(models.Model):
    name = models.CharField(max_length=100, unique=True)
    capacity = models.IntegerField()
    location = models.CharField(max_length=255)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    
    def __str__(self):
        return f"{self.name} ({self.location})"


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
    day_of_week = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    recurring = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.course.title} - {self.get_day_of_week_display()} ({self.start_time}-{self.end_time})"
    
    class Meta:
        unique_together = (
            ('hall', 'day_of_week', 'start_time'),
        )


class Booking(models.Model):
    PURPOSE_CHOICES = (
        ('course', 'Course'),
        ('tutoring', 'Tutoring'),
        ('meeting', 'Meeting')
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
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_requested')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_as_student', 
                               null=True, blank=True, limit_choices_to={'user_type': 'student'})
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_as_tutor',
                             null=True, blank=True, limit_choices_to={'user_type': 'teacher'})
    
    def __str__(self):
        return f"{self.get_purpose_display()} - {self.hall.name} ({self.start_datetime})"
    
    class Meta:
        ordering = ['-start_datetime']