from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Lesson, Homework, Attendance
from .serializers import LessonSerializer, HomeworkSerializer, AttendanceSerializer, LessonSummarySerializer
from django.db.models import Q
from core.permissions import IsTeacher, IsStudent, IsAdminOrReception
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
User = get_user_model()
# Create your views here.

class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='schedule_slot',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter lessons by schedule slot id',
                required=False
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        qs = Lesson.objects.select_related('course', 'schedule_slot')
        schedule_slot_id = self.request.query_params.get('schedule_slot')
        if schedule_slot_id:
            # Only show if user is teacher for slot or enrolled in slot
            slot_filter = Q(schedule_slot_id=schedule_slot_id)
            if hasattr(user, 'user_type') and user.user_type == 'teacher':
                allowed = qs.filter(slot_filter & Q(schedule_slot__teacher=user)).exists()
            elif hasattr(user, 'user_type') and user.user_type == 'student':
                allowed = qs.filter(slot_filter & Q(schedule_slot__enrollments__student=user)).exists()
            else:
                allowed = False
            if not allowed:
                return qs.none()
            qs = qs.filter(schedule_slot_id=schedule_slot_id)
        else:
            if hasattr(user, 'user_type') and user.user_type == 'teacher':
                qs = qs.filter(course__schedule_slots__teacher=user).distinct()
            elif hasattr(user, 'user_type') and user.user_type == 'student':
                qs = qs.filter(course__enrollments__student=user).distinct()
            else:
                qs = qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='schedule_slot',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter summary by schedule slot id',
                required=True
            )
        ],
        responses={200: LessonSummarySerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        schedule_slot_id = request.query_params.get('schedule_slot')
        if not schedule_slot_id:
            return Response({'detail': 'schedule_slot is required.'}, status=400)
        user = request.user
        lessons = Lesson.objects.filter(schedule_slot_id=schedule_slot_id).select_related('schedule_slot')
        allowed = False
        if hasattr(user, 'user_type') and user.user_type == 'teacher':
            allowed = lessons.filter(schedule_slot__teacher=user).exists()
        elif hasattr(user, 'user_type') and user.user_type == 'student':
            allowed = lessons.filter(schedule_slot__enrollments__student=user).exists()
        if not allowed:
            return Response([], status=200)
        serializer = LessonSummarySerializer(lessons, many=True, context={'request': request})
        return Response(serializer.data)

class HomeworkViewSet(viewsets.ModelViewSet):
    serializer_class = HomeworkSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='lesson',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter homework by lesson id',
                required=False
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        qs = Homework.objects.select_related('lesson', 'lesson__course', 'lesson__schedule_slot')
        lesson_id = self.request.query_params.get('lesson')
        if lesson_id:
            # Only show if user is teacher for lesson's slot or enrolled in lesson's slot
            lesson_filter = Q(lesson_id=lesson_id)
            if hasattr(user, 'user_type') and user.user_type == 'teacher':
                allowed = qs.filter(lesson_filter & Q(lesson__schedule_slot__teacher=user)).exists()
            elif hasattr(user, 'user_type') and user.user_type == 'student':
                allowed = qs.filter(lesson_filter & Q(lesson__schedule_slot__enrollments__student=user)).exists()
            else:
                allowed = False
            if not allowed:
                return qs.none()
            qs = qs.filter(lesson_id=lesson_id)
        else:
            if hasattr(user, 'user_type') and user.user_type == 'teacher':
                qs = qs.filter(lesson__schedule_slot__teacher=user)
            elif hasattr(user, 'user_type') and user.user_type == 'student':
                qs = qs.filter(lesson__course__enrollments__student=user).distinct()
            elif hasattr(user, 'user_type') and user.user_type in ['admin', 'reception']:
                pass
            else:
                qs = qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save()

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related('student', 'lesson', 'lesson__course', 'teacher')
        if hasattr(user, 'user_type') and user.user_type == 'teacher':
            qs = qs.filter(lesson__schedule_slot__teacher=user)
        elif hasattr(user, 'user_type') and user.user_type == 'student':
            qs = qs.filter(student=user)
        elif hasattr(user, 'user_type') and user.user_type in ['admin', 'reception']:
            pass
        else:
            qs = qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'records': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'student': {'type': 'integer'},
                                'lesson': {'type': 'integer'},
                                'attendance': {'type': 'string', 'enum': ['present', 'absent']},
                            },
                            'required': ['student', 'lesson', 'attendance']
                        }
                    }
                },
                'required': ['records']
            }
        },
        responses={201: AttendanceSerializer(many=True)}
    )
    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request):
        if not hasattr(request.user, 'user_type') or request.user.user_type != 'teacher':
            return Response({'detail': 'Only teachers can bulk create attendance.'}, status=status.HTTP_403_FORBIDDEN)
        records = request.data.get('records', [])
        if not isinstance(records, list) or not records:
            return Response({'detail': 'records must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        errors = []
        for rec in records:
            data = rec.copy()
            data['teacher'] = request.user.id  # forcibly assign teacher
            serializer = AttendanceSerializer(data=data)
            if serializer.is_valid():
                # Use update_or_create to avoid duplicates
                obj, _ = Attendance.objects.update_or_create(
                    student_id=data['student'],
                    lesson_id=data['lesson'],
                    defaults={
                        'teacher': request.user,
                        'attendance': data['attendance'],
                    }
                )
                created.append(AttendanceSerializer(obj).data)
            else:
                errors.append({'record': rec, 'errors': serializer.errors})
        if errors:
            return Response({'created': created, 'errors': errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response(created, status=status.HTTP_201_CREATED)
