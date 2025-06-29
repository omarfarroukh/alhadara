from decimal import Decimal
from rest_framework import serializers
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking, Wishlist, Enrollment
from lessons.models import Lesson, Homework, Attendance
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Prefetch,Sum
from django.conf import settings
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


User = get_user_model()

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('id', 'name', 'description')
        
class CourseTypeSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    tags = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseType
        fields = ('id', 'name', 'department', 'department_name', 'tags')
    
    def get_tags(self, obj):
        return obj.get_tags()

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
    remaining_seats = serializers.SerializerMethodField()

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
    
    def get_remaining_seats(self, obj):
        """Calculate remaining available seats in the schedule slot"""
        if not obj.course:
            return None
            
        # Count active enrollments for this schedule slot
        active_enrollments = Enrollment.objects.filter(
            schedule_slot=obj,
            status__in=['pending', 'active']
        ).count()
        
        remaining = obj.course.max_students - active_enrollments
        return max(remaining, 0)  # Ensure we don't return negative numbers

    
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
    
class TeacherScheduleSlotSerializer(ScheduleSlotSerializer):
    """Serializer for teacher's schedule slots with enrolled students"""
    enrolled_students = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()
    course_progress = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    average_attendance_percentage = serializers.SerializerMethodField()
    
    class Meta(ScheduleSlotSerializer.Meta):
        fields = list(ScheduleSlotSerializer.Meta.fields) + ['enrolled_students', 'enrolled_count', 'course_progress', 'lessons_count', 'average_attendance_percentage']
    
    def get_enrolled_students(self, obj):
        """Get list of enrolled students for this schedule slot"""
        enrollments = obj.enrollments.filter(
            status__in=['pending', 'active']
        ).select_related('student')
        
        students = []
        for enrollment in enrollments:
            if enrollment.is_guest:
                # For guest enrollments, use the stored name fields
                student_name = f"{enrollment.first_name} {enrollment.last_name}".strip()
                if enrollment.middle_name:
                    student_name = f"{enrollment.first_name} {enrollment.middle_name} {enrollment.last_name}".strip()
            else:
                # For regular students, use the user's full name
                student_name = enrollment.student.get_full_name() if enrollment.student else "Unknown"
            
            students.append({
                'id': enrollment.id,
                'name': student_name,
                'is_guest': enrollment.is_guest,
            })
        
        return students
    
    def get_enrolled_count(self, obj):
        """Get count of enrolled students for this schedule slot"""
        return obj.enrollments.filter(status__in=['pending', 'active']).count()

    def get_course_progress(self, obj):
        from datetime import datetime, date
        slot = obj
        if not slot or not slot.start_time or not slot.end_time:
            return 0.0
        slot_duration = (datetime.combine(date.today(), slot.end_time) - datetime.combine(date.today(), slot.start_time)).total_seconds() / 3600
        completed_count = obj.lessons_in_lessons_app.filter(status='completed').count()
        course_hours = obj.course.duration
        if course_hours > 0 and slot_duration > 0:
            progress = (completed_count * slot_duration) / course_hours * 100
            return round(min(progress, 100), 2)
        return 0.0

    def get_lessons_count(self, obj):
        return Lesson.objects.filter(schedule_slot=obj, course=obj.course).count()

    def get_average_attendance_percentage(self, obj):
        from lessons.models import Attendance, Lesson
        completed_lessons = Lesson.objects.filter(schedule_slot=obj, status='completed')
        if not completed_lessons.exists():
            return 0.0
        lesson_attendance_rates = []
        for lesson in completed_lessons:
            total_enrollments = Attendance.objects.filter(lesson=lesson).count()
            if total_enrollments == 0:
                lesson_attendance_rates.append(0.0)
                continue
            present_count = Attendance.objects.filter(lesson=lesson, attendance='present').count()
            lesson_attendance_rates.append(present_count / total_enrollments)
        avg = sum(lesson_attendance_rates) / len(lesson_attendance_rates) * 100
        return round(avg, 2)

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
        if not obj.schedule_slot:
            return None
        return {
            'course_title': obj.schedule_slot.course.title if obj.schedule_slot.course else None,
            'days_of_week': obj.schedule_slot.days_of_week,
            'days_display': ", ".join(obj.schedule_slot.days_of_week),
            'time_range': {
                'start': obj.schedule_slot.start_time.strftime('%H:%M') if obj.schedule_slot.start_time else None,
                'end': obj.schedule_slot.end_time.strftime('%H:%M') if obj.schedule_slot.end_time else None,
                'display': (
                    f"{obj.schedule_slot.start_time.strftime('%H:%M')}-"
                    f"{obj.schedule_slot.end_time.strftime('%H:%M')}"
                ) if obj.schedule_slot.start_time and obj.schedule_slot.end_time else None
            },
            'validity_period': {
                'start': obj.schedule_slot.valid_from.strftime('%Y-%m-%d') if obj.schedule_slot.valid_from else None,
                'end': obj.schedule_slot.valid_until.strftime('%Y-%m-%d') if obj.schedule_slot.valid_until else None,
                'display': (
                    f"From {obj.schedule_slot.valid_from.strftime('%Y-%m-%d')} to "
                    f"{obj.schedule_slot.valid_until.strftime('%Y-%m-%d')}"
                ) if obj.schedule_slot.valid_from and obj.schedule_slot.valid_until else None
            }
        }

    def get_remaining_balance(self, obj):
        return obj.course.price - obj.amount_paid

class StudentEnrollmentSerializer(BaseEnrollmentSerializer):
    course_progress = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    attendance_percentage = serializers.SerializerMethodField()
    class Meta(BaseEnrollmentSerializer.Meta):
        read_only_fields = BaseEnrollmentSerializer.Meta.read_only_fields + (
            'first_name', 'middle_name', 'last_name', 'phone', 'is_guest',
            'payment_method', 'course_progress', 'lessons_count', 'attendance_percentage'
        )
        fields = BaseEnrollmentSerializer.Meta.fields + ('course_progress', 'lessons_count', 'attendance_percentage')

    def get_course_progress(self, obj):
        # obj is Enrollment
        from datetime import datetime, date
        lessons = Lesson.objects.filter(schedule_slot=obj.schedule_slot, course=obj.course, status__in=['in_progress', 'completed'])
        slot = obj.schedule_slot
        if not slot or not slot.start_time or not slot.end_time:
            return 0.0
        slot_duration = (datetime.combine(date.today(), slot.end_time) - datetime.combine(date.today(), slot.start_time)).total_seconds() / 3600
        completed_count = lessons.count()
        course_hours = obj.course.duration
        if course_hours > 0 and slot_duration > 0:
            progress = (completed_count * slot_duration) / course_hours * 100
            return round(min(progress, 100), 2)
        return 0.0

    def get_lessons_count(self, obj):
        return Lesson.objects.filter(schedule_slot=obj.schedule_slot, course=obj.course).count()

    def get_attendance_percentage(self, obj):
        # Only consider completed lessons
        from lessons.models import Attendance, Lesson
        completed_lessons = Lesson.objects.filter(schedule_slot=obj.schedule_slot, course=obj.course, status='completed')
        total = completed_lessons.count()
        if total == 0:
            return 0.0
        attended = Attendance.objects.filter(
            lesson__in=completed_lessons,
            enrollment=obj,
            attendance='present'
        ).count()
        return round((attended / total) * 100, 2)

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
    
    
# class ActiveCourseForStudentSerializer(serializers.ModelSerializer):
#     """Serializer for active courses from student perspective (based on enrollments)"""
#     course_progress = serializers.SerializerMethodField()
#     student_attendance = serializers.SerializerMethodField()
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     course_description = serializers.CharField(source='course.description', read_only=True)
#     course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
#     course_duration = serializers.IntegerField(source='course.duration', read_only=True)
#     course_category = serializers.CharField(source='course.category', read_only=True)
#     course_certification_eligible = serializers.BooleanField(source='course.certification_eligible', read_only=True)
    
#     department_name = serializers.CharField(source='course.department.name', read_only=True)
#     course_type_name = serializers.CharField(source='course.course_type.name', read_only=True)
    
#     # Schedule information
#     hall_name = serializers.CharField(source='schedule_slot.hall.name', read_only=True)
#     hall_location = serializers.CharField(source='schedule_slot.hall.location', read_only=True)
#     teacher_name = serializers.SerializerMethodField()
#     days_of_week = serializers.ListField(source='schedule_slot.days_of_week', read_only=True)
#     start_time = serializers.TimeField(source='schedule_slot.start_time', read_only=True)
#     end_time = serializers.TimeField(source='schedule_slot.end_time', read_only=True)
#     valid_from = serializers.DateField(source='schedule_slot.valid_from', read_only=True)
#     valid_until = serializers.DateField(source='schedule_slot.valid_until', read_only=True)
    
#     # Enrollment information
#     enrollment_status = serializers.CharField(source='status', read_only=True)
#     payment_status = serializers.CharField(read_only=True)
#     amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
#     remaining_balance = serializers.SerializerMethodField()
#     enrollment_date = serializers.DateTimeField(read_only=True)
    
#     # Lesson information
#     lessons = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Enrollment
#         fields = [
#             'id',
#             'course_title',
#             'course_description',
#             'course_price',
#             'course_duration',
#             'course_category',
#             'course_certification_eligible',
#             'department_name',
#             'course_type_name',
#             'hall_name',
#             'hall_location',
#             'teacher_name',
#             'days_of_week',
#             'start_time',
#             'end_time',
#             'valid_from',
#             'valid_until',
#             'enrollment_status',
#             'payment_status',
#             'amount_paid',
#             'remaining_balance',
#             'enrollment_date',
#             'lessons',
#             'course_progress',
#             'student_attendance', 
#         ]
#     def get_course_progress(self, obj):
#         """Calculate course progress using schedule slot durations"""
#         try:
#             completed_lessons = Lesson.objects.filter(
#                 course=obj.course,
#                 schedule_slot=obj.schedule_slot,
#                 status='completed'
#             )
            
#             # Calculate total hours using the duration_hours property
#             total_lesson_hours = sum(
#                 lesson.duration_hours for lesson in completed_lessons
#             )
            
#             total_course_hours = obj.course.duration
            
#             if total_course_hours > 0:
#                 progress = (total_lesson_hours / total_course_hours) * 100
#                 return round(min(progress, 100), 1)  # Cap at 100%
            
#             return 0
#         except Exception as e:
#             logger.error(f"Progress calculation error: {str(e)}")
#             return 0
        
#     def get_student_attendance(self, obj):
#         """Calculate student attendance percentage based on attended lesson durations"""
#         try:
#             # Get all lessons that have been conducted (completed or in_progress)
#             conducted_lessons = Lesson.objects.filter(
#                 course=obj.course,
#                 schedule_slot=obj.schedule_slot,
#                 status__in=['completed', 'in_progress']
#             ).prefetch_related('attendance_records')
            
#             if not conducted_lessons.exists():
#                 return 0
            
#             total_duration = 0
#             attended_duration = 0
            
#             for lesson in conducted_lessons:
#                 lesson_duration = lesson.duration_hours  # Using the property we created earlier
#                 total_duration += lesson_duration
                
#                 # Check if student attended this lesson
#                 if lesson.attendance_records.filter(
#                     student=obj.student,
#                     attendance='present'
#                 ).exists():
#                     attended_duration += lesson_duration
            
#             if total_duration > 0:
#                 attendance_percentage = (attended_duration / total_duration) * 100
#                 return round(min(attendance_percentage, 100), 1)  # Cap at 100%
            
#             return 0
#         except Exception as e:
#             logger.error(f"Error calculating student attendance: {str(e)}")
#             return 0
#     def get_teacher_name(self, obj):
#         """Get teacher's full name"""
#         if obj.schedule_slot and obj.schedule_slot.teacher:
#             return obj.schedule_slot.teacher.get_full_name()
#         return None
    
#     def get_remaining_balance(self, obj):
#         """Calculate remaining balance for the course"""
#         return obj.course.price - obj.amount_paid
    
#     def get_lessons(self, obj):
#         """Get all lessons for this course/schedule slot combination"""
#         lessons = Lesson.objects.filter(
#             course=obj.course,
#             schedule_slot=obj.schedule_slot
#         ).order_by('lesson_order', 'lesson_date')
        
#         return SimpleLessonSerializer(lessons, many=True, context=self.context).data


# class ActiveCourseForTeacherSerializer(serializers.ModelSerializer):
#     """Serializer for active courses from teacher perspective (based on schedule slots)"""
    
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     course_description = serializers.CharField(source='course.description', read_only=True)
#     course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
#     course_duration = serializers.IntegerField(source='course.duration', read_only=True)
#     course_category = serializers.CharField(source='course.category', read_only=True)
#     course_max_students = serializers.IntegerField(source='course.max_students', read_only=True)
#     course_certification_eligible = serializers.BooleanField(source='course.certification_eligible', read_only=True)
    
#     department_name = serializers.CharField(source='course.department.name', read_only=True)
#     course_type_name = serializers.CharField(source='course.course_type.name', read_only=True)
    
#     # Schedule information
#     hall_name = serializers.CharField(source='hall.name', read_only=True)
#     hall_location = serializers.CharField(source='hall.location', read_only=True)
#     hall_capacity = serializers.IntegerField(source='hall.capacity', read_only=True)
#     days_of_week = serializers.ListField(read_only=True)
#     start_time = serializers.TimeField(read_only=True)
#     end_time = serializers.TimeField(read_only=True)
#     valid_from = serializers.DateField(read_only=True)
#     valid_until = serializers.DateField(read_only=True)
#     recurring = serializers.BooleanField(read_only=True)
    
#     # Student information
#     enrolled_students_count = serializers.SerializerMethodField()
#     enrolled_students = serializers.SerializerMethodField()
    
#     # Add lessons field
#     lessons = serializers.SerializerMethodField()
#     course_progress = serializers.SerializerMethodField()
    
#     # Update the Meta fields to include course_progress
#     class Meta:
#         model = ScheduleSlot
#         fields = [
#             'id',
#             'course_title',
#             'course_description',
#             'course_price',
#             'course_duration',
#             'course_category',
#             'course_max_students',
#             'course_certification_eligible',
#             'department_name',
#             'course_type_name',
#             'hall_name',
#             'hall_location',
#             'hall_capacity',
#             'days_of_week',
#             'start_time',
#             'end_time',
#             'valid_from',
#             'valid_until',
#             'recurring',
#             'enrolled_students_count',
#             'enrolled_students',
#             'lessons',
#             'course_progress',  # Add this line
#         ]
    
#     # Add this new method
#     def get_course_progress(self, obj):
#         """Calculate course progress based on completed lessons vs total course duration"""
#         try:
#             # Get all completed lessons for this schedule slot
#             completed_lessons = Lesson.objects.filter(
#                 course=obj.course,
#                 schedule_slot=obj,
#                 status='completed'
#             )
            
#             # Calculate total hours from completed lessons
#             total_completed_hours = 0
#             for lesson in completed_lessons:
#                 # Use the duration_hours property we created earlier
#                 total_completed_hours += lesson.duration_hours
            
#             # Get total course duration (in hours)
#             total_course_hours = obj.course.duration
            
#             if total_course_hours > 0:
#                 progress_percentage = (total_completed_hours / total_course_hours) * 100
#                 return round(min(progress_percentage, 100), 1)  # Cap at 100%
            
#             return 0
#         except Exception as e:
#             logger.error(f"Error calculating course progress: {str(e)}")
#             return 0
#     def get_enrolled_students_count(self, obj):
#         """Get count of enrolled students for this schedule slot"""
#         return obj.enrollments.filter(
#             status__in=['pending', 'active']
#         ).count()
    
#     def get_enrolled_students(self, obj):
#         """Get list of enrolled students for this schedule slot"""
#         enrollments = obj.enrollments.filter(
#             status__in=['pending', 'active']
#         ).select_related('student')
        
#         return [
#             {
#                 'id': enrollment.student.id,
#                 'name': enrollment.student.get_full_name(),
#                 'phone': enrollment.student.phone,
#                 'enrollment_status': enrollment.status,
#                 'payment_status': enrollment.payment_status,
#                 'enrollment_date': enrollment.enrollment_date
#             }
#             for enrollment in enrollments
#         ]
    
#     def get_lessons(self, obj):
#         """Get all lessons for this schedule slot"""
#         from .serializers import SimpleLessonSerializer
        
#         lessons = Lesson.objects.filter(
#             schedule_slot=obj,
#             course=obj.course
#         ).order_by('lesson_date', 'lesson_order')
        
#         # Pass request context to serializer if available
#         context = {}
#         if hasattr(self, 'context'):
#             context = self.context
        
#         return SimpleLessonSerializer(lessons, many=True, context=context).data
    
#     def to_representation(self, instance):
#         try:
#             return super().to_representation(instance)
#         except Exception as e:
#             logger.error(f"Serialization error: {str(e)}")
#             return {
#                 'error': 'Could not serialize course data',
#                 'course_id': instance.id if hasattr(instance, 'id') else None
#             }

# class ActiveCourseForAdminSerializer(serializers.ModelSerializer):
#     """Comprehensive serializer for admin view of all active courses"""
    
#     # Course information
#     course_id = serializers.IntegerField(source='course.id', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     course_description = serializers.CharField(source='course.description', read_only=True)
#     course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
#     course_duration = serializers.IntegerField(source='course.duration', read_only=True)
#     course_category = serializers.CharField(source='course.category', read_only=True)
#     course_max_students = serializers.IntegerField(source='course.max_students', read_only=True)
#     course_certification_eligible = serializers.BooleanField(source='course.certification_eligible', read_only=True)
#     course_created_at = serializers.DateTimeField(source='course.created_at', read_only=True)
    
#     # Department and course type
#     department_id = serializers.IntegerField(source='course.department.id', read_only=True)
#     department_name = serializers.CharField(source='course.department.name', read_only=True)
#     course_type_id = serializers.IntegerField(source='course.course_type.id', read_only=True)
#     course_type_name = serializers.CharField(source='course.course_type.name', read_only=True)
    
#     # Teacher information
#     teacher_id = serializers.IntegerField(source='teacher.id', read_only=True)
#     teacher_name = serializers.SerializerMethodField()
#     teacher_phone = serializers.CharField(source='teacher.phone', read_only=True)
    
#     # Hall information
#     hall_id = serializers.IntegerField(source='hall.id', read_only=True)
#     hall_name = serializers.CharField(source='hall.name', read_only=True)
#     hall_location = serializers.CharField(source='hall.location', read_only=True)
#     hall_capacity = serializers.IntegerField(source='hall.capacity', read_only=True)
    
#     # Schedule information
#     schedule_slot_id = serializers.IntegerField(source='id', read_only=True)
#     days_of_week = serializers.ListField(read_only=True)
#     start_time = serializers.TimeField(read_only=True)
#     end_time = serializers.TimeField(read_only=True)
#     valid_from = serializers.DateField(read_only=True)
#     valid_until = serializers.DateField(read_only=True)
#     recurring = serializers.BooleanField(read_only=True)
#     created_at = serializers.DateTimeField(read_only=True)
#     updated_at = serializers.DateTimeField(read_only=True)
    
#     # Enrollment statistics
#     total_enrolled_students = serializers.SerializerMethodField()
#     active_enrollments = serializers.SerializerMethodField()
#     pending_enrollments = serializers.SerializerMethodField()
#     total_revenue = serializers.SerializerMethodField()
#     pending_payments = serializers.SerializerMethodField()
    
#     # Detailed enrollment information
#     enrolled_students = serializers.SerializerMethodField()
    
#     # Utilization metrics
#     capacity_utilization = serializers.SerializerMethodField()
#     enrollment_rate = serializers.SerializerMethodField()
    
#     class Meta:
#         model = ScheduleSlot
#         fields = [
#             # Course info
#             'course_id',
#             'course_title',
#             'course_description',
#             'course_price',
#             'course_duration',
#             'course_category',
#             'course_max_students',
#             'course_certification_eligible',
#             'course_created_at',
            
#             # Department and type
#             'department_id',
#             'department_name',
#             'course_type_id',
#             'course_type_name',
            
#             # Teacher info
#             'teacher_id',
#             'teacher_name',
#             'teacher_phone',
            
#             # Hall info
#             'hall_id',
#             'hall_name',
#             'hall_location',
#             'hall_capacity',
            
#             # Schedule info
#             'schedule_slot_id',
#             'days_of_week',
#             'start_time',
#             'end_time',
#             'valid_from',
#             'valid_until',
#             'recurring',
#             'created_at',
#             'updated_at',
            
#             # Statistics
#             'total_enrolled_students',
#             'active_enrollments',
#             'pending_enrollments',
#             'total_revenue',
#             'pending_payments',
#             'capacity_utilization',
#             'enrollment_rate',
            
#             # Detailed data
#             'enrolled_students'
#         ]
    
#     def get_teacher_name(self, obj):
#         """Get teacher's full name"""
#         if obj.teacher:
#             return obj.teacher.get_full_name()
#         return None
    
#     def get_total_enrolled_students(self, obj):
#         """Get total count of enrolled students"""
#         return obj.enrollments.filter(
#             status__in=['pending', 'active']
#         ).count()
    
#     def get_active_enrollments(self, obj):
#         """Get count of active enrollments"""
#         return obj.enrollments.filter(status='active').count()
    
#     def get_pending_enrollments(self, obj):
#         """Get count of pending enrollments"""
#         return obj.enrollments.filter(status='pending').count()
    
#     def get_total_revenue(self, obj):
#         """Calculate total revenue from this course"""
#         from decimal import Decimal
#         total = obj.enrollments.filter(
#             status__in=['pending', 'active']
#         ).aggregate(
#             total=Sum('amount_paid')
#         )['total'] or Decimal('0')
        
#         return str(total)
    
#     def get_pending_payments(self, obj):
#         """Calculate pending payments (remaining balance)"""
#         from decimal import Decimal
#         enrollments = obj.enrollments.filter(status__in=['pending', 'active'])
#         pending = Decimal('0')
        
#         for enrollment in enrollments:
#             remaining = enrollment.course.price - enrollment.amount_paid
#             if remaining > 0:
#                 pending += remaining
        
#         return str(pending)
    
#     def get_capacity_utilization(self, obj):
#         """Calculate hall capacity utilization percentage"""
#         enrolled = self.get_total_enrolled_students(obj)
#         if obj.hall and obj.hall.capacity > 0:
#             return round((enrolled / obj.hall.capacity) * 100, 1)
#         return 0
    
#     def get_enrollment_rate(self, obj):
#         """Calculate enrollment rate against course max students"""
#         enrolled = self.get_total_enrolled_students(obj)
#         if obj.course.max_students > 0:
#             return round((enrolled / obj.course.max_students) * 100, 1)
#         return 0
    
#     def get_enrolled_students(self, obj):
#         """Get detailed list of enrolled students"""
#         enrollments = obj.enrollments.filter(
#             status__in=['pending', 'active']
#         ).select_related('student').order_by('enrollment_date')
        
#         return [
#             {
#                 'enrollment_id': enrollment.id,
#                 'student_id': enrollment.student.id,
#                 'student_name': enrollment.student.get_full_name(),
#                 'student_phone': enrollment.student.phone,
#                 'enrollment_status': enrollment.status,
#                 'payment_status': enrollment.payment_status,
#                 'amount_paid': str(enrollment.amount_paid),
#                 'remaining_balance': str(enrollment.course.price - enrollment.amount_paid),
#                 'enrollment_date': enrollment.enrollment_date,
#                 'last_updated': enrollment.updated_at if hasattr(enrollment, 'updated_at') else None
#             }
#             for enrollment in enrollments
#         ]
    
#     def to_representation(self, instance):
#         try:
#             return super().to_representation(instance)
#         except Exception as e:
#             logger.error(f"Admin serialization error: {str(e)}")
#             return {
#                 'error': 'Could not serialize course data',
#                 'schedule_slot_id': instance.id if hasattr(instance, 'id') else None,
#                 'course_title': instance.course.title if hasattr(instance, 'course') else 'Unknown'
#             }

#     def to_representation(self, instance):
#         try:
#             return super().to_representation(instance)
#         except Exception as e:
#             logger.error(f"Admin serialization error for course {instance.course.title if hasattr(instance, 'course') else 'unknown'}: {str(e)}", exc_info=True)
#             return {
#                 'error': 'Could not serialize course data',
#                 'details': str(e) if settings.DEBUG else None,
#                 'schedule_slot_id': instance.id if hasattr(instance, 'id') else None,
#                 'course_title': instance.course.title if hasattr(instance, 'course') else 'Unknown'}    

# class LessonSerializer(serializers.ModelSerializer):
#     """
#     Serializer for Lesson model - used by both teachers and students
#     """
#     teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     file_name = serializers.CharField(read_only=True)
#     file_size = serializers.IntegerField(read_only=True)
#     homework_count = serializers.SerializerMethodField()
#     attendance_count = serializers.SerializerMethodField()
#     my_attendance = serializers.SerializerMethodField()
    
#     course = serializers.PrimaryKeyRelatedField(
#         queryset=Course.objects.all(),
#         required=True
#     )
#     schedule_slot = serializers.PrimaryKeyRelatedField(
#         queryset=ScheduleSlot.objects.all(),
#         required=True
#     )

#     class Meta:
#         model = Lesson
#         fields = [
#             'id',
#             'title',
#             'notes',
#             'file',
#             'file_name',
#             'file_size',
#             'link',
#             'course',
#             'course_title',
#             'schedule_slot',
#             'teacher',
#             'teacher_name',
#             'lesson_order',
#             'lesson_date',

#             'status',
#             'homework_count',
#             'attendance_count',
#             'my_attendance',
#             'created_at',
#             'updated_at'
#         ]
#         read_only_fields = ['teacher', 'created_at', 'updated_at']
    
#     def get_homework_count(self, obj):
#         """Get count of homework assignments for this lesson"""
#         return obj.homework_assignments.count()
    
#     def get_attendance_count(self, obj):
#         """Get count of attendance records for this lesson"""
#         return obj.attendance_records.count()
    
#     def get_my_attendance(self, obj):
#         """Get student's attendance for this lesson (only for student views)"""
#         request = self.context.get('request')
#         if request and hasattr(request, 'user') and request.user.user_type == 'student':
#             try:
#                 attendance = obj.attendance_records.get(student=request.user)
#                 return {
#                     'attendance': attendance.attendance,
#                     'notes': attendance.notes,
#                     'recorded_at': attendance.recorded_at
#                 }
#             except Attendance.DoesNotExist:
#                 return None
#         return None
    
#     def validate(self, data):
#         """Validate lesson data"""
#         # Ensure teacher owns the course/schedule slot
#         request = self.context.get('request')
#         if request and hasattr(request, 'user'):
#             user = request.user
            
#             # Skip validation for students (read-only for them)
#             if user.user_type == 'student':
#                 return data
                
#             # Check if updating existing lesson
#             if self.instance:
#                 if self.instance.teacher != user:
#                     raise serializers.ValidationError("You can only edit your own lessons.")
            
#             # For new lessons, validate course/schedule slot ownership
#             schedule_slot = data.get('schedule_slot')
#             if schedule_slot and schedule_slot.teacher != user:
#                 raise serializers.ValidationError("You can only create lessons for courses you teach.")
        
#         return data
    
#     def to_representation(self, instance):
#         """Customize representation based on user type"""
#         representation = super().to_representation(instance)
#         request = self.context.get('request')
        
#         if request and hasattr(request, 'user'):
#             user = request.user
#             if user.user_type == 'student':
#                 # Remove fields that students shouldn't see
#                 representation.pop('teacher', None)
#                 representation.pop('schedule_slot', None)
#                 representation.pop('course', None)
        
#         return representation

# class SimpleLessonSerializer(serializers.ModelSerializer):
#     """Simplified lesson serializer with proper expired homework handling"""
#     file_name = serializers.CharField(read_only=True)
#     file_size = serializers.IntegerField(read_only=True)
#     homework_assignments = serializers.SerializerMethodField()
#     attendance = serializers.SerializerMethodField()

#     class Meta:
#         model = Lesson
#         fields = [
#             'id',
#             'title',
#             'notes',
#             'file',
#             'file_name',
#             'file_size',
#             'link',
#             'lesson_order', 
#             'lesson_date',
#             'status',
#             'homework_assignments',
#             'attendance',
#             'created_at',
#             'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']

#     def get_attendance(self, obj):
#         """Get student's attendance status for this lesson"""
#         request = self.context.get('request')
#         if request and hasattr(request, 'user') and request.user.user_type == 'student':
#             attendance = obj.attendance_records.filter(student=request.user).first()
#             return attendance.attendance if attendance else None
#         return None

#     def get_homework_assignments(self, obj):
#         """Get published homework assignments with proper expired status"""
#         homework = obj.homework_assignments.filter(status='published')
        
#         class SimpleHomeworkSerializer(serializers.ModelSerializer):
#             is_overdue = serializers.SerializerMethodField()
#             days_until_deadline = serializers.SerializerMethodField()
#             deadline_status = serializers.SerializerMethodField()  # New field

#             class Meta:
#                 model = Homework
#                 fields = [
#                     'id',
#                     'title',
#                     'description',
#                     'form_link',
#                     'deadline',
#                     'max_score',
#                     'is_mandatory',
#                     'is_overdue',
#                     'days_until_deadline',
#                     'deadline_status'  # Include new field
#                 ]

#             def get_is_overdue(self, obj):
#                 return obj.deadline < timezone.now()

#             def get_days_until_deadline(self, obj):
#                 """Return None if expired, days remaining if not"""
#                 if obj.deadline < timezone.now():
#                     return None
#                 return (obj.deadline - timezone.now()).days

#             def get_deadline_status(self, obj):
#                 """Return 'expired' if overdue, None if still active"""
#                 return "expired" if obj.deadline < timezone.now() else None

#         return SimpleHomeworkSerializer(homework, many=True, context=self.context).data

# class HomeworkSerializer(serializers.ModelSerializer):
#     """
#     Unified serializer for Homework model without submission fields
#     """
#     teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
#     lesson_title = serializers.CharField(source='lesson.title', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     is_overdue = serializers.BooleanField(read_only=True)
#     days_until_deadline = serializers.IntegerField(read_only=True)
#     is_expired = serializers.SerializerMethodField()
#     # Lesson field - writable during creation
#     lesson = serializers.PrimaryKeyRelatedField(
#         queryset=Lesson.objects.all(),
#         required=False  # Not required for updates
#     )

#     # Course field - read-only (set automatically from lesson)
#     course = serializers.PrimaryKeyRelatedField(
#         read_only=True
#     )

#     class Meta:
#         model = Homework
#         fields = [
#             'id',
#             'title',
#             'description',
#             'form_link',
#             'deadline',
#             'lesson',
#             'lesson_title',
#             'course',
#             'course_title',
#             'teacher',
#             'teacher_name',
#             'max_score',
#             'is_mandatory',
#             'status',
#             'is_overdue',
#             'days_until_deadline',
#             'created_at',
#             'updated_at',
#             'is_expired'
#         ]
#         read_only_fields = [
#             'teacher', 
#             'created_at', 
#             'updated_at',
#             'course',
#             'status',
#             'is_expired'
#         ]
#         extra_kwargs = {
#             'title': {'required': True},
#             'description': {'required': True},
#             'deadline': {'required': True},
#             'form_link': {'required': False},
#             'max_score': {'required': False},
#             'is_mandatory': {'required': False},
#         }
#     def get_is_expired(self, obj):
#         return obj.deadline < timezone.now
#     def validate(self, data):
#         """Validate homework data based on user type and action"""
#         request = self.context.get('request')
#         if not request:
#             return data

#         user = request.user
#         action = self.context.get('view').action if hasattr(self.context.get('view'), 'action') else None

#         if action in ['create', 'update', 'partial_update']:
#             if user.user_type != 'teacher':
#                 raise serializers.ValidationError("Only teachers can create or update homework.")

#             if action == 'create' and data.get('deadline') and data['deadline'] <= timezone.now():
#                 raise serializers.ValidationError("Deadline must be in the future.")

#             if self.instance and self.instance.teacher != user:
#                 raise serializers.ValidationError("You can only edit your own homework assignments.")

#             if action == 'create':
#                 lesson = data.get('lesson')
#                 if not lesson:
#                     raise serializers.ValidationError("Lesson is required.")
#                 if lesson.teacher != user:
#                     raise serializers.ValidationError("You can only create homework for your own lessons.")

#         return data

#     def create(self, validated_data):
#         """Handle homework creation"""
#         request = self.context.get('request')
#         if not request or request.user.user_type != 'teacher':
#             raise serializers.ValidationError("Only teachers can create homework.")

#         lesson = validated_data.pop('lesson')
#         homework = Homework.objects.create(
#             **validated_data,
#             teacher=request.user,
#             course=lesson.course,
#             lesson=lesson,
#             status='published'
#         )
#         return homework
#     def to_representation(self, instance):
#         """Completely hide expired homework from students"""
#         data = super().to_representation(instance)
#         request = self.context.get('request')
        
#         if request and request.user.user_type == 'student' and instance.deadline < timezone.now():
#             return None  # This will remove the homework from the response
        
#         return data

# class UnifiedAttendanceSerializer(serializers.ModelSerializer):
#     """
#     Unified serializer for Attendance model that handles:
#     - Creation (teacher)
#     - Teacher view
#     - Student view
#     - Bulk operations
#     """
#     student_name = serializers.CharField(source='student.get_full_name', read_only=True)
#     student_phone = serializers.CharField(source='student.phone', read_only=True)
#     lesson_title = serializers.CharField(source='lesson.title', read_only=True)
#     lesson_date = serializers.DateField(source='lesson.lesson_date', read_only=True)
#     course_title = serializers.CharField(source='course.title', read_only=True)
#     teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)

#     class Meta:
#         model = Attendance
#         fields = [
#             'id',
#             'student', 'student_name', 'student_phone',
#             'course', 'course_title',
#             'lesson', 'lesson_title', 'lesson_date',
#             'teacher', 'teacher_name',
#             'attendance',
#             'notes',
#             'recorded_at',
#             'updated_at'
#         ]
#         read_only_fields = ['teacher', 'recorded_at', 'updated_at']
#         extra_kwargs = {
#             'student': {'required': True},
#             'course': {'required': True},
#             'lesson': {'required': True},
#             'attendance': {'required': True},
#             'notes': {'required': False}
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         request = self.context.get('request')
#         action = self.context.get('view').action if self.context.get('view') else None

#         # Different field sets based on action and user type
#         if request and hasattr(request, 'user'):
#             user = request.user
            
#             if action == 'create' and user.user_type == 'teacher':
#                 # Limit querysets for creation
#                 self.fields['course'].queryset = Course.objects.filter(
#                     schedule_slots__teacher=user
#                 ).distinct()
#                 self.fields['lesson'].queryset = Lesson.objects.filter(
#                     teacher=user
#                 )
#                 self.fields['student'].queryset = User.objects.filter(
#                     user_type='student',
#                     enrollments__course__in=self.fields['course'].queryset,
#                     enrollments__status__in=['pending', 'active']
#                 ).distinct()
            
#             elif user.user_type == 'student':
#                 # Student view - only show relevant fields
#                 self.fields.pop('student', None)
#                 self.fields.pop('student_phone', None)
#                 self.fields.pop('teacher', None)
#                 self.fields.pop('teacher_name', None)

#     def validate(self, data):
#         """Comprehensive validation for all cases"""
#         request = self.context.get('request')
#         if not request or not hasattr(request, 'user'):
#             return data

#         user = request.user
#         action = self.context.get('view').action if self.context.get('view') else None

#         # Teacher validation for create/update
#         if user.user_type == 'teacher' and action in ['create', 'update', 'partial_update']:
#             lesson = data.get('lesson', getattr(self.instance, 'lesson', None))
#             course = data.get('course', getattr(self.instance, 'course', None))
#             student = data.get('student', getattr(self.instance, 'student', None))

#             if lesson and lesson.teacher != user:
#                 raise serializers.ValidationError("You can only record attendance for lessons you teach.")

#             if student and course:
#                 from .models import Enrollment
#                 if not Enrollment.objects.filter(
#                     student=student,
#                     course=course,
#                     status__in=['pending', 'active']
#                 ).exists():
#                     raise serializers.ValidationError("Student is not enrolled in this course.")

#             if lesson and course and lesson.course != course:
#                 raise serializers.ValidationError("Selected lesson does not belong to the selected course.")

#         return data

#     def to_representation(self, instance):
#         """Custom representation based on user type"""
#         data = super().to_representation(instance)
#         request = self.context.get('request')
        
#         if request and hasattr(request, 'user') and request.user.user_type == 'student':
#             # Student view - only show limited fields
#             return {
#                 'id': data['id'],
#                 'course_title': data['course_title'],
#                 'lesson_title': data['lesson_title'],
#                 'lesson_date': data['lesson_date'],
#                 'teacher_name': data['teacher_name'],
#                 'attendance': data['attendance'],
#                 'notes': data['notes'],
#                 'recorded_at': data['recorded_at']
#             }
        
#         return data

# class BulkAttendanceSerializer(serializers.Serializer):
#     """
#     Serializer for bulk attendance recording
#     """
#     lesson = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all())
#     course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.none())
#     attendance_records = serializers.ListField(
#         child=serializers.DictField(
#             child=serializers.CharField()
#         ),
#         min_length=1
#     )
#     def validate(self, data):
#         """Validate bulk attendance data including enrollment checks"""
#         request = self.context.get('request')
#         if request and hasattr(request, 'user'):
#             user = request.user
#             lesson = data['lesson']
#             course = data['course']
            
#             if lesson.teacher != user:
#                 raise serializers.ValidationError("You can only record attendance for lessons you teach.")
            
#             # Check all students are enrolled
#             from .models import Enrollment
#             student_ids = [r['student_id'] for r in data['attendance_records']]
#             enrolled_students = set(Enrollment.objects.filter(
#                 student_id__in=student_ids,
#                 course=course,
#                 status__in=['pending', 'active']
#             ).values_list('student_id', flat=True))
            
#             for record in data['attendance_records']:
#                 if record['student_id'] not in enrolled_students:
#                     raise serializers.ValidationError(
#                         f"Student {record['student_id']} is not enrolled in this course"
#                     )
        
#         return data
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         request = self.context.get('request')
#         if request and hasattr(request, 'user'):
#             self.fields['course'].queryset = Course.objects.filter(
#                 schedule_slots__teacher=request.user
#             ).distinct()
#             self.fields['lesson'].queryset = Lesson.objects.filter(
#                 teacher=request.user
#             )
    
#     def validate_attendance_records(self, value):
#         """Validate attendance records format"""
#         required_fields = ['student_id', 'attendance']
#         for record in value:
#             for field in required_fields:
#                 if field not in record:
#                     raise serializers.ValidationError(f"Missing field: {field}")
            
#             if record['attendance'] not in ['present', 'absent']:
#                 raise serializers.ValidationError(
#                     f"Invalid attendance value: {record['attendance']}. Must be 'present' or 'absent'"
#                 )
        
#         return value
    
#     def validate(self, data):
#         """Validate bulk attendance data"""
#         request = self.context.get('request')
#         if request and hasattr(request, 'user'):
#             user = request.user
#             lesson = data['lesson']
            
#             if lesson.teacher != user:
#                 raise serializers.ValidationError("You can only record attendance for lessons you teach.")
        
#         return data
    
#     def create(self, validated_data):
#         """Create bulk attendance records"""
#         request = self.context.get('request')
#         teacher = request.user if request and hasattr(request, 'user') else None
        
#         lesson = validated_data['lesson']
#         course = validated_data['course']
#         attendance_records = validated_data['attendance_records']
        
#         results = []
#         for record_data in attendance_records:
#             try:
#                 student = User.objects.get(id=record_data['student_id'])
                
#                 attendance, created = Attendance.objects.update_or_create(
#                     student=student,
#                     lesson=lesson,
#                     defaults={
#                         'course': course,
#                         'teacher': teacher,
#                         'attendance': record_data['attendance'],
#                         'notes': record_data.get('notes', '')
#                     }
#                 )
                
#                 results.append({
#                     'student_id': student.id,
#                     'student_name': student.get_full_name(),
#                     'attendance': attendance.attendance,
#                     'created': created
#                 })
                
#             except User.DoesNotExist:
#                 results.append({
#                     'student_id': record_data['student_id'],
#                     'error': 'Student not found'
#                 })
        
#         return {
#             'lesson_id': lesson.id,
#             'lesson_title': lesson.title,
#             'total_records': len(results),
#             'results': results
#         }