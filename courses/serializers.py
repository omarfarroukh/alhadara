from decimal import Decimal
from rest_framework import serializers
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking,Wishlist, Enrollment
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('id', 'name', 'description')
        
class CourseTypeSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    
    class Meta:
        model = CourseType
        fields = ('id', 'name', 'department', 'department_name')

class HallSerializer(serializers.ModelSerializer):
    hourly_rate = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=Decimal('0.01')  # Use Decimal instance for min_value
    )
    class Meta:
        model = Hall
        fields = ('id', 'name', 'capacity', 'location', 'hourly_rate')
    
    def validate(self, data):
        """
        Use Django model validation by creating a temporary instance
        This ensures the same validation rules apply to both API and admin
        """
        # Create a temporary instance for validation
        instance = self.instance or Hall()
        
        # Update instance with validated data
        for key, value in data.items():
            setattr(instance, key, value)
        
        # Run model validation
        try:
            instance.clean()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, 'message_dict'):
                # Field-specific errors
                raise serializers.ValidationError(e.message_dict)
            else:
                # General errors
                raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        
        return data
    
class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    course_type_name = serializers.ReadOnlyField(source='course_type.name')
    
    class Meta:
        model = Course
        fields = (
            'id', 'title', 'description', 'price', 'duration', 
            'max_students', 'certification_eligible', 'department', 
            'department_name', 'course_type', 'course_type_name', 'category'
        )
    def validate(self, data):
        """
        Use Django model validation by creating a temporary instance
        This ensures the same validation rules apply to both API and admin
        """
        # Create a temporary instance for validation
        instance = self.instance or Course()
        
        # Update instance with validated data
        for key, value in data.items():
            setattr(instance, key, value)
        
        # Run model validation
        try:
            instance.clean()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, 'message_dict'):
                # Field-specific errors
                raise serializers.ValidationError(e.message_dict)
            else:
                # General errors
                raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        
        return data        

class ScheduleSlotSerializer(serializers.ModelSerializer):
    course_title = serializers.ReadOnlyField(source='course.title')
    hall_name = serializers.ReadOnlyField(source='hall.name')
    teacher_name = serializers.SerializerMethodField()
    duration_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduleSlot
        fields = (
            'id', 'course', 'course_title', 'hall', 'hall_name', 'teacher', 'teacher_name',
            'days_of_week', 'start_time', 'end_time', 'duration_hours',
            'recurring', 'valid_from', 'valid_until'
        )
        extra_kwargs = {
            'valid_until': {'required': False},
            'teacher': {'required': False}
        }
    
    def get_teacher_name(self, obj):
        """Get teacher's full name instead of username"""
        if obj.teacher:
            return obj.teacher.get_full_name()
        return None
    
    def get_duration_hours(self, obj):
        """Calculate duration in hours including minutes"""
        duration = (obj.end_time.hour - obj.start_time.hour) + \
                  (obj.end_time.minute - obj.start_time.minute)/60
        return round(duration, 2)

    def validate_days_of_week(self, value):
        """Validate the days_of_week field"""
        if not value:
            raise serializers.ValidationError("At least one day must be selected")
            
        valid_days = [choice[0] for choice in ScheduleSlot.DAY_CHOICES]
        for day in value:
            if day not in valid_days:
                raise serializers.ValidationError(f"'{day}' is not a valid day choice")
        return value
    
    def validate(self, data):
        """
        Use Django model validation by creating a temporary instance
        This ensures the same validation rules apply to both API and admin
        """
        # Create a temporary instance for validation
        instance = self.instance or ScheduleSlot()
        
        # Update instance with validated data
        for key, value in data.items():
            setattr(instance, key, value)
        
        # Run model validation
        try:
            instance.clean()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, 'message_dict'):
                # Field-specific errors
                raise serializers.ValidationError(e.message_dict)
            else:
                # General errors
                raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        
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

class WishlistCourseSerializer(serializers.ModelSerializer):
    course_type_name = serializers.ReadOnlyField(source='course_type.name')
    department_name = serializers.ReadOnlyField(source='department.name')
    
    class Meta:
        model = Course
        fields = (
            'id', 'title', 'description', 'price', 'duration',
            'course_type_name', 'department_name', 'category'
        )

class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.get_full_name')
    course_title = serializers.ReadOnlyField(source='course.title')
    schedule_slot_display = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = (
            'id', 'student', 'student_name', 'course', 'course_title',
            'schedule_slot', 'schedule_slot_display', 'status', 'payment_status',
            'enrollment_date', 'amount_paid', 'remaining_balance', 'notes'
        )
        read_only_fields = ('enrollment_date', 'status', 'payment_status', 'amount_paid', 'student')
    
    def get_schedule_slot_display(self, obj):
        if obj.schedule_slot:
            # Custom format without teacher's name
            days = ", ".join(obj.schedule_slot.days_of_week)
            return f"{obj.schedule_slot.course.title} - {days} {obj.schedule_slot.start_time.strftime('%H:%M')}-{obj.schedule_slot.end_time.strftime('%H:%M')}"
        return None
    
    def get_remaining_balance(self, obj):
        return obj.course.price - obj.amount_paid
    
    def validate(self, data):
        """
        Use Django model validation by creating a temporary instance
        This ensures the same validation rules apply to both API and admin
        """
        # Create a temporary instance for validation
        instance = self.instance or Enrollment()
        
        # Update instance with validated data
        for key, value in data.items():
            setattr(instance, key, value)
        
        # Set student from request user
        if not self.instance:  # Only on creation
            instance.student = self.context['request'].user
        
        # Run model validation
        try:
            instance.clean()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, 'message_dict'):
                # Field-specific errors
                raise serializers.ValidationError(e.message_dict)
            else:
                # General errors
                raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        
        return data

class WishlistSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()
    workshops = serializers.SerializerMethodField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'courses', 'workshops', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_courses(self, obj):
        courses = obj.courses.filter(category='course')
        return WishlistCourseSerializer(courses, many=True).data
    
    def get_workshops(self, obj):
        workshops = obj.courses.filter(category='workshop')
        return WishlistCourseSerializer(workshops, many=True).data