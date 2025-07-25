from rest_framework import serializers

from core.services import upload_to_telegram
from .models import Lesson, Homework, Attendance, HomeworkGrade, ScheduleSlotNews, PrivateLessonRequest, PrivateLessonProposedOption
from courses.models import Enrollment
from datetime import date
from django.contrib.auth import get_user_model
from core.models import FileStorage
from core.serializers import FileStorageSerializer
User = get_user_model()

class LessonSerializer(serializers.ModelSerializer):
    has_homework = serializers.SerializerMethodField()
    file = serializers.FileField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Upload lesson materials (PDF, DOC, PPT, etc.)"
    )
    file_storage_details = FileStorageSerializer(
        source='file_storage',
        read_only=True
    )

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'notes', 'file', 'file_storage_details', 'link',
            'course', 'schedule_slot', 'lesson_order', 'lesson_date',
            'status', 'created_at', 'updated_at', 'has_homework'
        ]
        read_only_fields = [
            'id', 'created_at', 'lesson_order', 'updated_at', 'has_homework'
        ]
    
    def get_has_homework(self, obj):
        return obj.homework_assignments_in_lessons_app.exists()
    
    def validate(self, data):
        schedule_slot = data.get('schedule_slot') or getattr(self.instance, 'schedule_slot', None)
        course = data.get('course') or getattr(self.instance, 'course', None)
        lesson_date = data.get('lesson_date') or getattr(self.instance, 'lesson_date', None)
        lesson_order = data.get('lesson_order') or getattr(self.instance, 'lesson_order', None)
        
        # Validate that schedule_slot belongs to the course
        if schedule_slot and course:
            if schedule_slot.course != course:
                raise serializers.ValidationError(
                    {'schedule_slot': 'The selected schedule slot does not belong to the specified course.'}
                )
        
        # Validate slot date range
        if schedule_slot and lesson_date:
            if schedule_slot.valid_from and lesson_date < schedule_slot.valid_from:
                raise serializers.ValidationError('Lesson date cannot be before the schedule slot start date.')
            if schedule_slot.valid_until and lesson_date > schedule_slot.valid_until:
                raise serializers.ValidationError('Lesson date cannot be after the schedule slot end date.')
        
        # Validate lesson order
        if lesson_order and lesson_order > 1 and schedule_slot and lesson_date:
            from .models import Lesson
            prev_lesson = Lesson.objects.filter(
                course=course,
                schedule_slot=schedule_slot,
                lesson_order=lesson_order-1
            ).first()
            if prev_lesson and lesson_date <= prev_lesson.lesson_date:
                raise serializers.ValidationError(f'Lesson {lesson_order} date must be after lesson {lesson_order-1} date.')
        
        # Existing slot ended check
        if schedule_slot and schedule_slot.valid_until and schedule_slot.valid_until < date.today():
            raise serializers.ValidationError('Cannot create a lesson for a schedule slot that has ended.')
        
        return data

    def create(self, validated_data):
        uploaded_file = validated_data.pop('file', None)
        file_storage = None

        if uploaded_file:
            if uploaded_file.size == 0:
                raise serializers.ValidationError(
                    {"file": "Cannot upload an empty file."}
                )
            try:
                result = upload_to_telegram(uploaded_file)
                file_storage = FileStorage.objects.create(
                    file=uploaded_file,
                    telegram_file_id=result['file_id'],
                    telegram_download_link=result['download_link'],
                    uploaded_by=self.context['request'].user
                )
            except Exception as e:
                raise serializers.ValidationError({"file": str(e)})

        # auto lesson_order, etc.
        schedule_slot = validated_data.get('schedule_slot')
        if validated_data.get('lesson_order') is None:
            last = Lesson.objects.filter(schedule_slot=schedule_slot).order_by('-lesson_order').first()
            validated_data['lesson_order'] = (last.lesson_order + 1) if last else 1

        validated_data['file_storage'] = file_storage
        return Lesson.objects.create(**validated_data)
    
    
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
        deadline = data.get('deadline') or getattr(self.instance, 'deadline', None)
        if lesson and deadline:
            if deadline.date() <= lesson.lesson_date:
                raise serializers.ValidationError('Homework deadline must be at least one day after the lesson date.')
        return data

class AttendanceSerializer(serializers.ModelSerializer):
    enrollment = serializers.PrimaryKeyRelatedField(queryset=Enrollment.objects.all(), required=True)
    student_name = serializers.SerializerMethodField()
    lesson_title = serializers.ReadOnlyField(source='lesson.title')
    class Meta:
        model = Attendance
        fields = [
            'id', 'enrollment', 'student_name', 'lesson', 'lesson_title',
            'teacher', 'attendance', 'recorded_at', 'updated_at'
        ]
        read_only_fields = ['id', 'recorded_at', 'updated_at', 'student_name', 'lesson_title']

    def get_student_name(self, obj):
        return obj.enrollment.student.get_full_name() if obj.enrollment and obj.enrollment.student else None

    def validate(self, data):
        lesson = data.get('lesson') or getattr(self.instance, 'lesson', None)
        if lesson and lesson.status not in ['scheduled', 'completed']:
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
        fields = ['id', 'title', 'lesson_date','lesson_order', 'status', 'homework', 'attended', 'attendance_rate']

    def get_attended(self, obj):
        user = self.context.get('request').user
        if hasattr(user, 'user_type') and user.user_type == 'student':
            # Find the enrollment for this user, course, and schedule_slot
            enrollment = Enrollment.objects.filter(student=user, course=obj.course, schedule_slot=obj.schedule_slot).first()
            if not enrollment:
                return False
            return obj.attendance_records_in_lessons_app.filter(enrollment=enrollment, attendance='present').exists()
        return None

    def get_attendance_rate(self, obj):
        user = self.context.get('request').user
        if hasattr(user, 'user_type') and user.user_type == 'teacher':
            total = obj.attendance_records_in_lessons_app.count()
            present = obj.attendance_records_in_lessons_app.filter(attendance='present').count()
            return round((present / total) * 100, 2) if total > 0 else 0.0
        return None

class HomeworkGradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    
    class Meta:
        model = HomeworkGrade
        fields = ['id', 'homework', 'enrollment', 'grade', 'comment', 'graded_by', 'graded_at', 'student_name']
        read_only_fields = ['id', 'graded_by', 'graded_at', 'student_name', 'homework']
    
    def get_student_name(self, obj):
        # Use the enrollment's student_name logic that already handles guest cases
        if obj.enrollment:
            if hasattr(obj.enrollment, 'is_guest') and obj.enrollment.is_guest:
                return f"{obj.enrollment.first_name} {obj.enrollment.middle_name} {obj.enrollment.last_name}"
            elif obj.enrollment.student:
                return obj.enrollment.student.get_full_name()
        return "Unknown Student"
    
    def validate(self, data):
        homework = self.context.get('homework')
        if homework and 'grade' in data:
            if data['grade'] > homework.max_score:
                raise serializers.ValidationError({
                    'grade': f'Grade cannot exceed homework max score of {homework.max_score}'
                })
        return data


class ScheduleSlotNewsSerializer(serializers.ModelSerializer):
    file_storage = serializers.PrimaryKeyRelatedField(
        queryset=FileStorage.objects.all(), required=False, allow_null=True
    )
    file_storage_details = FileStorageSerializer(source='file_storage', read_only=True)
    
    class Meta:
        model = ScheduleSlotNews
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'author', 'file_storage_details']

class PrivateLessonProposedOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivateLessonProposedOption
        fields = ['id', 'date', 'time_from', 'time_to', 'created_at']
        read_only_fields = ['id', 'created_at']

class PrivateLessonRequestSerializer(serializers.ModelSerializer):
    proposed_options = PrivateLessonProposedOptionSerializer(many=True, read_only=True)
    student_name = serializers.SerializerMethodField(read_only=True)
    student_phone = serializers.SerializerMethodField(read_only=True)
    slot_teacher_name = serializers.SerializerMethodField(read_only=True)
    slot_course_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PrivateLessonRequest
        fields = [
            'id', 'student', 'student_name', 'student_phone', 'schedule_slot', 'slot_teacher_name', 'slot_course_name',
            'preferred_date', 'preferred_time_from', 'preferred_time_to',
            'status', 'confirmed_date', 'confirmed_time_from', 'confirmed_time_to',
            'created_at', 'updated_at', 'proposed_options'
        ]
        read_only_fields = [
            'id', 'student', 'student_name', 'student_phone', 'status', 'confirmed_date', 'confirmed_time_from', 'confirmed_time_to',
            'created_at', 'updated_at', 'proposed_options', 'slot_teacher_name', 'slot_course_name'
        ]

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.get_full_name() if hasattr(obj.student, 'get_full_name') else str(obj.student)
        return None

    def get_student_phone(self, obj):
        if obj.student and hasattr(obj.student, 'phone'):
            return obj.student.phone
        return None

    def get_slot_teacher_name(self, obj):
        if obj.schedule_slot and obj.schedule_slot.teacher:
            return obj.schedule_slot.teacher.get_full_name() if hasattr(obj.schedule_slot.teacher, 'get_full_name') else str(obj.schedule_slot.teacher)
        return None

    def get_slot_course_name(self, obj):
        if obj.schedule_slot and obj.schedule_slot.course:
            return obj.schedule_slot.course.title
        return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        allowed_types = ['admin', 'reception']
        if not (user and hasattr(user, 'user_type') and user.user_type in allowed_types):
            rep.pop('student_name', None)
            rep.pop('student_phone', None)
            rep.pop('slot_teacher_name', None)
            rep.pop('slot_course_name', None)
        return rep