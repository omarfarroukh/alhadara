from rest_framework import serializers
from core.serializers import CustomUserSerializer
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ('id', 'name', 'code', 'description')


class CourseTypeSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    
    class Meta:
        model = CourseType
        fields = ('id', 'name', 'category', 'department', 'department_name')


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
            'teacher_name'
        )


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ('id', 'name', 'capacity', 'location', 'hourly_rate')


class ScheduleSlotSerializer(serializers.ModelSerializer):
    course_title = serializers.ReadOnlyField(source='course.title')
    hall_name = serializers.ReadOnlyField(source='hall.name')
    day_display = serializers.ReadOnlyField(source='get_day_of_week_display')
    
    class Meta:
        model = ScheduleSlot
        fields = (
            'id', 'course', 'course_title', 'hall', 'hall_name',
            'day_of_week', 'day_display', 'start_time', 'end_time',
            'recurring', 'valid_from', 'valid_until'
        )


class BookingSerializer(serializers.ModelSerializer):
    hall_name = serializers.ReadOnlyField(source='hall.name')
    requested_by_username = serializers.ReadOnlyField(source='requested_by.username')
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
            'tutor', 'tutor_username'
        )
        read_only_fields = ('requested_by',)
    
    def create(self, validated_data):
        validated_data['requested_by'] = self.context['request'].user
        return super().create(validated_data)