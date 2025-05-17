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
    
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be positive")
        return value
    
    def validate_max_students(self, value):
        if value <= 0:
            raise serializers.ValidationError('Max students must be positive')
        return value

class HallSerializer(serializers.ModelSerializer):
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
    
    class Meta:
        model = ScheduleSlot
        fields = (
            'id', 'course', 'course_title', 'hall', 'hall_name',
            'days_of_week', 'start_time', 'end_time',
            'recurring', 'valid_from', 'valid_until'
        )
    
    
    def validate_days_of_week(self, value):
        valid_days = [choice[0] for choice in ScheduleSlot.DAY_CHOICES]
        for day in value:
            if day not in valid_days:
                raise serializers.ValidationError(f"'{day}' is not a valid day choice")
        return value
    
    def validate(self, data):
        
        valid_from = data.get('valid_from', getattr(self.instance, 'valid_from', None))
        valid_until = data.get('valid_until', getattr(self.instance, 'valid_until', None))
        
        if valid_from and valid_from < date.today() and not self.instance:
            raise serializers.ValidationError("Cannot schedule in the past")
            
        if valid_until and valid_from and valid_until < valid_from:
            raise serializers.ValidationError("End date must be after start date")
            
        if data.get('recurring', True) and not valid_until:
            raise serializers.ValidationError("Recurring slots require an end date")
        course = data.get('course')
        hall = data.get('hall')
        
        if course and hall:
            if course.max_students > hall.capacity:
                raise serializers.ValidationError(
                    f"Course maximum students ({course.max_students}) "
                    f"exceeds hall capacity ({hall.capacity})"
                )
        
        # Check if end time is after start time
        if data['start_time'] >= data['end_time']:
            raise serializers.ValidationError("End time must be after start time")
        
        # Check for overlapping schedule slots
        if 'hall' in data and 'days_of_week' in data and 'start_time' in data and 'end_time' in data:
            hall = data['hall']
            days = data['days_of_week']
            start_time = data['start_time']
            end_time = data['end_time']
            
            # Get existing slots that overlap with any of the days
            overlapping_slots = ScheduleSlot.objects.filter(
                hall=hall,
                days_of_week__overlap=days,  # Checks for any day overlap
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(id=self.instance.id if self.instance else None)
            
            # For recurring slots, check date ranges
            if data.get('recurring', True):
                valid_from = data.get('valid_from', self.instance.valid_from if self.instance else None)
                valid_until = data.get('valid_until', self.instance.valid_until if self.instance else None)
                
                if valid_until and valid_from > valid_until:
                    raise serializers.ValidationError("Valid until date must be after valid from date")
                
                overlapping_slots = overlapping_slots.filter(
                    models.Q(valid_until__gte=valid_from) | 
                    models.Q(valid_until__isnull=True))
                
                if valid_until:
                    overlapping_slots = overlapping_slots.filter(
                        valid_from__lte=valid_until)
            
            if overlapping_slots.exists():
                raise serializers.ValidationError(
                    "The hall is already scheduled during one or more of these days/times")
        
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