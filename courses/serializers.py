from decimal import Decimal
from rest_framework import serializers
from core.serializers import CustomUserSerializer
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking
from django.db import models
from django.db.models import Q
from datetime import date
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('id', 'name', 'description')
        
    def validate_name(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters long.")
        return value


class CourseTypeSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    
    class Meta:
        model = CourseType
        fields = ('id', 'name', 'department', 'department_name')


class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    course_type_name = serializers.ReadOnlyField(source='course_type.name')
    teacher_name = serializers.ReadOnlyField(source='teacher.username', default=None)
    
    class Meta:
        model = Course
        fields = (
            'id', 'title', 'description', 'price', 'duration', 
            'max_students', 'certification_eligible', 'department', 
            'department_name', 'course_type', 'course_type_name', 'teacher',
            'teacher_name','category'
        )
    def validate(self, data):
        department = data.get('department')
        course_type = data.get('course_type')
        
        if course_type.department != department:
            raise serializers.ValidationError(
                "The selected course type does not belong to the specified department"
            )
        
        return data
    
    def validate_duration(self, value):
        """Ensure duration is at least 1 hour"""
        if value < 1:
            raise serializers.ValidationError("Duration must be at least 1 hour")
        return value
    
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be positive")
        return value
    
    def validate_max_students(self, value):
        if value <= 0:
            raise serializers.ValidationError('Max students must be positive')
        return value

class HallSerializer(serializers.ModelSerializer):
    hourly_rate = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=Decimal('0.01')  # Use Decimal instance for min_value
    )

    class Meta:
        model = Hall
        fields = ('id', 'name', 'capacity', 'location', 'hourly_rate')
        
    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Capacity must be positive")
        return value
    
    def validate_hourly_rate(self, value):
        if value <= 0:
            raise serializers.ValidationError("Hourly rate must be positive")
        return value


class ScheduleSlotSerializer(serializers.ModelSerializer):
    course_title = serializers.ReadOnlyField(source='course.title')
    hall_name = serializers.ReadOnlyField(source='hall.name')
    duration_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduleSlot
        fields = (
            'id', 'course', 'course_title', 'hall', 'hall_name',
            'days_of_week', 'start_time', 'end_time', 'duration_hours',
            'recurring', 'valid_from', 'valid_until'
        )
        extra_kwargs = {
            'valid_until': {'required': False}  # Not required for non-recurring
        }

    def get_duration_hours(self, obj):
        return (obj.end_time.hour - obj.start_time.hour) + \
               (obj.end_time.minute - obj.start_time.minute)/60

    def validate_days_of_week(self, value):
        if not value:
            raise serializers.ValidationError("At least one day must be selected")
            
        valid_days = [choice[0] for choice in ScheduleSlot.DAY_CHOICES]
        for day in value:
            if day not in valid_days:
                raise serializers.ValidationError(f"'{day}' is not a valid day choice")
        return value
    
    def validate(self, data):
        # Get fields from data or instance
        valid_from = data.get('valid_from', getattr(self.instance, 'valid_from', None))
        valid_until = data.get('valid_until', getattr(self.instance, 'valid_until', None))
        recurring = data.get('recurring', getattr(self.instance, 'recurring', True))
        days_of_week = data.get('days_of_week', getattr(self.instance, 'days_of_week', None))
        start_time = data.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = data.get('end_time', getattr(self.instance, 'end_time', None))
        course = data.get('course', getattr(self.instance, 'course', None))
        hall = data.get('hall', getattr(self.instance, 'hall', None))

        # Basic validations
        if valid_from and valid_from < date.today() and not self.instance:
            raise serializers.ValidationError("Cannot schedule in the past")
            
        if valid_until and valid_from and valid_until < valid_from:
            raise serializers.ValidationError("End date must be after start date")
            
        if recurring and not valid_until:
            raise serializers.ValidationError("Recurring slots require an end date")
            
        if not recurring and days_of_week and len(days_of_week) > 1:
            raise serializers.ValidationError(
                "Non-recurring slots can only have one day specified"
            )

        # Duration validation
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError("End time must be after start time")
                
            duration = (end_time.hour - start_time.hour) + \
                      (end_time.minute - start_time.minute)/60
            if duration > 8:  # Or use MAX_DURATION_HOURS constant
                raise serializers.ValidationError("Time slots cannot exceed 8 hours")

        # Course capacity vs hall capacity
        if course and hall and course.max_students > hall.capacity:
            raise serializers.ValidationError(
                f"Course capacity ({course.max_students}) "
                f"exceeds hall capacity ({hall.capacity})"
            )

        # Date range validation
        if valid_from and valid_until and (valid_until - valid_from).days > 365:
            raise serializers.ValidationError(
                "Schedule slots cannot span more than 1 year"
            )

        # Overlap detection (optimized)
        if hall and days_of_week and start_time and end_time:
            overlap_qs = ScheduleSlot.objects.filter(
                hall=hall,
                days_of_week__overlap=days_of_week,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            
            # Date range conditions
            if valid_from and valid_until:
                overlap_qs = overlap_qs.filter(
                    Q(valid_until__gte=valid_from) | Q(valid_until__isnull=True),
                    valid_from__lte=valid_until
                )
            elif valid_from:
                overlap_qs = overlap_qs.filter(
                    Q(valid_until__gte=valid_from) | Q(valid_until__isnull=True)
                )
            
            if self.instance:
                overlap_qs = overlap_qs.exclude(id=self.instance.id)
            
            if overlap_qs.exists():
                raise serializers.ValidationError(
                    "Hall already has scheduled slots during these times/days"
                )

        return data
class BookingSerializer(serializers.ModelSerializer):
    hall_name = serializers.ReadOnlyField(source='hall.name')
    requested_by_username = serializers.ReadOnlyField(source='requested_by.username', default=None)
    student_username = serializers.ReadOnlyField(source='student.username', default=None)
    tutor_username = serializers.ReadOnlyField(source='tutor.username', default=None)
    purpose_display = serializers.ReadOnlyField(source='get_purpose_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    
    class Meta:
        model = Booking
        fields = (
            'id', 'hall', 'hall_name', 'purpose', 'purpose_display',
            'status', 'status_display', 'start_datetime', 'end_datetime',
            'requested_by', 'requested_by_username', 'student', 'student_username',
            'tutor', 'tutor_username', 'guest_name', 'guest_email', 'guest_phone',
            'guest_organization', 'notes'
        )
        read_only_fields = ('requested_by', 'status')
    
    def validate(self, data):
        # Check if end time is after start time
        if data['start_datetime'] >= data['end_datetime']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check for overlapping bookings
        overlapping_bookings = Booking.objects.filter(
            hall=data['hall'],
            start_datetime__lt=data['end_datetime'],
            end_datetime__gt=data['start_datetime'],
            status='approved'
        ).exclude(id=self.instance.id if self.instance else None)
        
        if overlapping_bookings.exists():
            raise serializers.ValidationError("The hall is already booked for this time slot")
        
        # Check for overlapping schedule slots
        if data['start_datetime'].date() == data['end_datetime'].date():  # Single day booking
            day_of_week = data['start_datetime'].strftime('%a').lower()
            
            overlapping_slots = ScheduleSlot.objects.filter(
                hall=data['hall'],
                days_of_week__contains=[day_of_week],
                start_time__lt=data['end_datetime'].time(),
                end_time__gt=data['start_datetime'].time(),
                valid_from__lte=data['start_datetime'].date(),
                valid_until__gte=data['start_datetime'].date()
            )
            
            if overlapping_slots.exists():
                raise serializers.ValidationError(
                    "The hall is already scheduled for a course during this time")
        
        return data
    
    def create(self, validated_data):
        if self.context['request'].user.is_authenticated:
            validated_data['requested_by'] = self.context['request'].user
        return super().create(validated_data)