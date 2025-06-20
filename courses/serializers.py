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
    is_in_wishlist = serializers.SerializerMethodField()
    wishlist_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Course
        fields = (
            'id', 'title', 'description', 'price', 'duration', 
            'max_students', 'certification_eligible', 'department', 
            'department_name', 'course_type', 'course_type_name', 'category',
            'is_in_wishlist', 'wishlist_count'
        )
        
    def get_is_in_wishlist(self, obj):
        # Uses the prefetched current_user_wishlists
        if hasattr(obj, 'current_user_wishlists'):
            return len(obj.current_user_wishlists) > 0
        return False
    
    def get_wishlist_count(self, obj):
        # Count how many wishlists include this course
        return obj.wishlists.count()
    
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

class BaseEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    course_title = serializers.ReadOnlyField(source='course.title')
    schedule_slot_display = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = Enrollment
        fields = (
            'id', 'student', 'student_name', 'course', 'course_title',
            'schedule_slot', 'schedule_slot_display', 'status', 'payment_status',
            'payment_method', 'payment_method_display', 'enrollment_date', 
            'amount_paid', 'remaining_balance', 'is_guest',
            'first_name', 'middle_name', 'last_name', 'phone', 'enrolled_by'
        )
        read_only_fields = (
            'id', 'enrollment_date', 'status', 'payment_status', 
            'amount_paid', 'student_name', 'course_title',
            'schedule_slot_display', 'remaining_balance', 'payment_method_display',
            'enrolled_by', 'student'
        )

    def get_student_name(self, obj):
        if obj.is_guest:
            return f"{obj.first_name} {obj.last_name}"
        return obj.student.get_full_name() if obj.student else None

    def get_schedule_slot_display(self, obj):
        if obj.schedule_slot:
            days = ", ".join(obj.schedule_slot.days_of_week)
            valid_from = obj.schedule_slot.valid_from.strftime('%Y-%m-%d') if obj.schedule_slot.valid_from else "N/A"
            valid_until = obj.schedule_slot.valid_until.strftime('%Y-%m-%d') if obj.schedule_slot.valid_until else "N/A"
            return (
                f"{obj.schedule_slot.course.title} - {days} "
                f"{obj.schedule_slot.start_time.strftime('%H:%M')}-"
                f"{obj.schedule_slot.end_time.strftime('%H:%M')} "
                f"(From {valid_from} to {valid_until})"
            )
        return None

    def get_remaining_balance(self, obj):
        return obj.course.price - obj.amount_paid

class StudentEnrollmentSerializer(BaseEnrollmentSerializer):
    class Meta(BaseEnrollmentSerializer.Meta):
        read_only_fields = BaseEnrollmentSerializer.Meta.read_only_fields + (
            'first_name', 'middle_name', 'last_name', 'phone', 'is_guest',
            'payment_method'
        )

    def validate(self, data):
        data = super().validate(data)
        data['is_guest'] = False
        
        # Get user from context
        user = self.context['request'].user
        
        # Create temporary instance for validation
        instance = Enrollment(**data)
        
        # Auto-fill student info
        instance.student = user
        instance.first_name = user.first_name
        instance.middle_name = user.middle_name
        instance.last_name = user.last_name
        instance.phone = user.phone
        instance.payment_method = 'ewallet'
        
        try:
            instance.clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else str(e))
        
        return data

class GuestEnrollmentSerializer(BaseEnrollmentSerializer):
    cash_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        write_only=True,
        required=False
    )

    class Meta(BaseEnrollmentSerializer.Meta):
        fields = BaseEnrollmentSerializer.Meta.fields + ('cash_amount',)
        extra_kwargs = {
            'student': {'read_only': True},
            'is_guest': {'read_only': True},
            'payment_method': {'read_only': True},  # Prevent duplicate
            'first_name': {'required': True},
            'last_name': {'required': True},
            'phone': {'required': True}
        }

    def validate(self, data):
        # Remove fields that will be set automatically
        data.pop('student', None)
        data.pop('is_guest', None)
        data.pop('payment_method', None)  # Remove if present
        
            
        return data


# class EnrollmentSerializer(serializers.ModelSerializer):
#     student_name = serializers.ReadOnlyField(source='student.get_full_name')
#     course_title = serializers.ReadOnlyField(source='course.title')
#     schedule_slot_display = serializers.SerializerMethodField()
#     remaining_balance = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Enrollment
#         fields = (
#             'id', 'student', 'student_name', 'course', 'course_title',
#             'schedule_slot', 'schedule_slot_display', 'status', 'payment_status',
#             'enrollment_date', 'amount_paid', 'remaining_balance', 'notes'
#         )
#         read_only_fields = ('enrollment_date', 'status', 'payment_status', 'amount_paid', 'student')
    
#     def get_schedule_slot_display(self, obj):
#         if obj.schedule_slot:
#             days = ", ".join(obj.schedule_slot.days_of_week)
#             valid_from = obj.schedule_slot.valid_from.strftime('%Y-%m-%d') if obj.schedule_slot.valid_from else "N/A"
#             valid_until = obj.schedule_slot.valid_until.strftime('%Y-%m-%d') if obj.schedule_slot.valid_until else "N/A"
#             return (
#                 f"{obj.schedule_slot.course.title} - {days} {obj.schedule_slot.start_time.strftime('%H:%M')}-"
#                 f"{obj.schedule_slot.end_time.strftime('%H:%M')} (From {valid_from} to {valid_until})"
#             )
#         return None
    
#     def get_remaining_balance(self, obj):
#         return obj.course.price - obj.amount_paid
    
#     def validate(self, data):
#         """
#         Use Django model validation by creating a temporary instance
#         This ensures the same validation rules apply to both API and admin
#         """
#         # Create a temporary instance for validation
#         instance = self.instance or Enrollment()
        
#         # Update instance with validated data
#         for key, value in data.items():
#             setattr(instance, key, value)
        
#         # Set student from request user
#         if not self.instance:  # Only on creation
#             instance.student = self.context['request'].user
        
#         # Run model validation
#         try:
#             instance.clean()
#         except ValidationError as e:
#             # Convert Django ValidationError to DRF ValidationError
#             if hasattr(e, 'message_dict'):
#                 # Field-specific errors
#                 raise serializers.ValidationError(e.message_dict)
#             else:
#                 # General errors
#                 raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        
#         return data

class WishlistSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()
    workshops = serializers.SerializerMethodField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'courses', 'workshops', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_courses(self, obj):
        courses = obj.courses.filter(category='course').select_related(
            'course_type', 'department'
        )
        return WishlistCourseSerializer(courses, many=True).data
    
    def get_workshops(self, obj):
        workshops = obj.courses.filter(category='workshop').select_related(
            'course_type', 'department'
        )
        return WishlistCourseSerializer(workshops, many=True).data

class HallFreeSlotSerializer(serializers.Serializer):
    start = serializers.TimeField(format="%H:%M")
    end = serializers.TimeField(format="%H:%M")

class HallFreePeriodSerializer(serializers.Serializer):
    start = serializers.TimeField(format="%H:%M")
    end = serializers.TimeField(format="%H:%M")
    slots = HallFreeSlotSerializer(many=True)

class HallAvailabilityResponseSerializer(serializers.Serializer):
    date = serializers.DateField()
    hall_id = serializers.IntegerField()
    hall_name = serializers.CharField()
    free_periods = HallFreePeriodSerializer(many=True)