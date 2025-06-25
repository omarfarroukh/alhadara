from rest_framework import serializers
from .models import Lesson, Homework, Attendance
from datetime import date
from django.contrib.auth import get_user_model
User = get_user_model()

class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'notes', 'file', 'link', 'course', 'schedule_slot',
            'lesson_order', 'lesson_date', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        schedule_slot = data.get('schedule_slot') or getattr(self.instance, 'schedule_slot', None)
        if schedule_slot and schedule_slot.valid_until and schedule_slot.valid_until < date.today():
            raise serializers.ValidationError('Cannot create a lesson for a schedule slot that has ended.')
        return data

class HomeworkSerializer(serializers.ModelSerializer):
    teacher = serializers.ReadOnlyField(source='teacher.id')
    course = serializers.ReadOnlyField(source='course.id')
    class Meta:
        model = Homework
        fields = [
            'id', 'title', 'description', 'form_link', 'deadline', 'lesson',
            'course', 'teacher', 'max_score', 'is_mandatory', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'teacher', 'course', 'status']

    def validate(self, data):
        lesson = data.get('lesson') or getattr(self.instance, 'lesson', None)
        if lesson and lesson.status in ['scheduled', 'cancelled']:
            raise serializers.ValidationError('Cannot assign homework to a lesson that is scheduled or cancelled.')
        return data

class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.ReadOnlyField(source='student.get_full_name')
    lesson_title = serializers.ReadOnlyField(source='lesson.title')
    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'lesson', 'lesson_title',
            'teacher', 'attendance', 'recorded_at', 'updated_at'
        ]
        read_only_fields = ['id', 'recorded_at', 'updated_at', 'student_name', 'lesson_title']

    def validate(self, data):
        lesson = data.get('lesson') or getattr(self.instance, 'lesson', None)
        if lesson and lesson.status not in ['in_progress', 'completed']:
            raise serializers.ValidationError('Can only record attendance for lessons that are in progress or completed.')
        return data

class HomeworkMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ['id', 'title']

class LessonSummarySerializer(serializers.ModelSerializer):
    homework = HomeworkMiniSerializer(many=True, source='homework_assignments_in_lessons_app')
    attended = serializers.SerializerMethodField()
    attendance_rate = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'lesson_date', 'homework', 'attended', 'attendance_rate']

    def get_attended(self, obj):
        user = self.context.get('request').user
        if hasattr(user, 'user_type') and user.user_type == 'student':
            return obj.attendance_records_in_lessons_app.filter(student=user, attendance='present').exists()
        return None

    def get_attendance_rate(self, obj):
        user = self.context.get('request').user
        if hasattr(user, 'user_type') and user.user_type == 'teacher':
            total = obj.attendance_records_in_lessons_app.count()
            present = obj.attendance_records_in_lessons_app.filter(attendance='present').count()
            return round((present / total) * 100, 2) if total > 0 else 0.0
        return None
