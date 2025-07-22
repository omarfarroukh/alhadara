from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Lesson, Homework, Attendance, HomeworkGrade
from .serializers import LessonSerializer, HomeworkSerializer, AttendanceSerializer, LessonSummarySerializer, HomeworkGradeSerializer
from django.db.models import Q
from core.permissions import IsReception, IsStudent, IsTeacher,IsReceptionOrStudent
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, inline_serializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .serializers import ScheduleSlotNewsSerializer
from .models import ScheduleSlotNews
from courses.models import ScheduleSlot
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser
from rest_framework.views import APIView
from rest_framework import mixins, viewsets
from .serializers import PrivateLessonRequestSerializer, PrivateLessonProposedOptionSerializer
from .models import PrivateLessonRequest, PrivateLessonProposedOption
from core.services import upload_to_telegram
from core.models import FileStorage
import logging
logger = logging.getLogger(__name__)
User = get_user_model()
# Create your views here.

class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy','bulk']:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]
    
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
        # The serializer already uploaded the file and filled file_storage
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
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy','bulk']:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]
    
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
    @extend_schema(
        request=HomeworkGradeSerializer,
        responses=HomeworkGradeSerializer(many=True),
        description="List all enrolled students and their grades for this homework"
    )
    @action(detail=True, methods=['get'], url_path='grades')
    def grades(self, request, pk=None):
        """Get grades - all for teachers, only own for students."""
        homework = self.get_object()
        lesson = homework.lesson
        user = request.user

        if hasattr(user, 'user_type'):
            if user.user_type == 'teacher':
                # Teacher sees all grades
                slot_teacher = getattr(lesson.schedule_slot, 'teacher', None)
                if user != slot_teacher:
                    return Response(
                        {'detail': 'Only the assigned teacher can view grades.'}, 
                        status=403
                    )
                
                enrollments = lesson.schedule_slot.enrollments.filter(status='active')
                grades = HomeworkGrade.objects.filter(homework=homework)
                grade_map = {g.enrollment_id: g for g in grades}
                
                result = []
                for enrollment in enrollments:
                    grade_obj = grade_map.get(enrollment.id)
                    if grade_obj:
                        result.append(grade_obj)
                    else:
                        # Create an unsaved HomeworkGrade instance for serializer
                        result.append(HomeworkGrade(
                            homework=homework,
                            enrollment=enrollment,
                            grade=None,
                            comment='',
                            graded_by=None,
                            graded_at=None
                        ))
                return Response(HomeworkGradeSerializer(result, many=True).data)

            elif user.user_type == 'student':
                # Student sees only their own grade
                enrollment = lesson.schedule_slot.enrollments.filter(student=user, status='active').first()
                if not enrollment:
                    return Response(
                        {'detail': 'You are not enrolled in this class.'}, 
                        status=403
                    )
                
                grade = HomeworkGrade.objects.filter(
                    homework=homework,
                    enrollment=enrollment
                ).first()
                
                if not grade:
                    # Return empty grade record if not graded yet
                    grade = HomeworkGrade(
                        homework=homework,
                        enrollment=enrollment,
                        grade=None,
                        comment='',
                        graded_by=None,
                        graded_at=None
                    )
                
                return Response(HomeworkGradeSerializer(grade).data)

        return Response(
            {'detail': 'You do not have permission to view grades.'}, 
            status=403
        )
    
    @extend_schema(
        request=HomeworkGradeSerializer,
        responses=HomeworkGradeSerializer,
        description="Grade a single student for this homework",
        examples=[
            OpenApiExample(
                'Example request',
                value={
                    'enrollment': 1,
                    'grade': 85,
                    'comment': 'Good work!'
                },
                request_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='grade')
    def grade(self, request, pk=None):
        """Grade a single student for this homework."""
        homework = self.get_object()
        lesson = homework.lesson
        slot_teacher = getattr(lesson.schedule_slot, 'teacher', None)
        if not (hasattr(request.user, 'user_type') and request.user.user_type == 'teacher' and request.user == slot_teacher):
            return Response({'detail': 'Only the assigned teacher can grade.'}, status=403)
        
        # Use serializer for request validation
        serializer = HomeworkGradeSerializer(data=request.data, context={
            'request': request,
            'homework': homework
        })
        serializer.is_valid(raise_exception=True)
        
        # Create or update the grade
        obj, _ = HomeworkGrade.objects.update_or_create(
            homework=homework,
            enrollment=serializer.validated_data['enrollment'],
            defaults={
                'grade': serializer.validated_data['grade'],
                'comment': serializer.validated_data.get('comment', ''),
                'graded_by': request.user,
            }
        )
        return Response(HomeworkGradeSerializer(obj).data)
    
    @extend_schema(
        request=inline_serializer(
            name='BulkGradeRequest',
            fields={
                'records': HomeworkGradeSerializer(many=True)
            }
        ),
        responses=inline_serializer(
            name='BulkGradeResponse',
            fields={
                'graded': HomeworkGradeSerializer(many=True),
                'errors': serializers.ListField(child=serializers.DictField())
            }
        ),
        description="Bulk grade students for this homework",
        examples=[
            OpenApiExample(
                'Example request',
                value={
                    'records': [
                        {
                            'enrollment': 1,
                            'grade': 85,
                            'comment': 'Good work!'
                        },
                        {
                            'enrollment': 2,
                            'grade': 90,
                            'comment': 'Excellent!'
                        }
                    ]
                },
                request_only=True
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='bulk-grade')
    def bulk_grade(self, request, pk=None):
        """Bulk grade students for this homework."""
        homework = self.get_object()
        lesson = homework.lesson
        slot_teacher = getattr(lesson.schedule_slot, 'teacher', None)
        if not (hasattr(request.user, 'user_type') and request.user.user_type == 'teacher' and request.user == slot_teacher):
            return Response({'detail': 'Only the assigned teacher can grade.'}, status=403)
        
        # Handle both direct array and {records: array} formats
        grade_records = request.data.get('records', request.data)
        if not isinstance(grade_records, list):
            return Response({'detail': 'Expected a list of grade records.'}, status=400)
        
        results = []
        errors = []
        for record in grade_records:
            serializer = HomeworkGradeSerializer(data=record, context={
                'request': request,
                'homework': homework
            })
            if not serializer.is_valid():
                errors.append({
                    'record': record,
                    'errors': serializer.errors
                })
                continue
                
            obj, _ = HomeworkGrade.objects.update_or_create(
                homework=homework,
                enrollment=serializer.validated_data['enrollment'],
                defaults={
                    'grade': serializer.validated_data['grade'],
                    'comment': serializer.validated_data.get('comment', ''),
                    'graded_by': request.user,
                }
            )
            results.append(obj)
        
        data = HomeworkGradeSerializer(results, many=True).data
        if errors:
            return Response({'graded': data, 'errors': errors}, status=207)
        return Response(data)

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy','bulk','bulk_create']:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related('enrollment', 'lesson', 'lesson__course', 'teacher')
        if hasattr(user, 'user_type') and user.user_type == 'teacher':
            qs = qs.filter(lesson__schedule_slot__teacher=user)
        elif hasattr(user, 'user_type') and user.user_type == 'student':
            qs = qs.filter(enrollment__student=user)
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
                                'enrollment': {'type': 'integer'},
                                'lesson': {'type': 'integer'},
                                'attendance': {'type': 'string', 'enum': ['present', 'absent']},
                            },
                            'required': ['enrollment', 'lesson', 'attendance']
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
                    enrollment_id=data['enrollment'],
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

class NewsFeedView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='scheduleslot',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID of the schedule slot to fetch news for',
                required=True
            )
        ],
        responses=ScheduleSlotNewsSerializer(many=True),
        description="List all news feed items for a given schedule slot. Only accessible to enrolled students and the assigned teacher."
    )
    def get(self, request):
        slot_id = request.query_params.get('scheduleslot')
        if not slot_id:
            return Response({'detail': 'scheduleslot query param required.'}, status=400)
        try:
            slot = ScheduleSlot.objects.get(id=slot_id)
        except ScheduleSlot.DoesNotExist:
            return Response({'detail': 'ScheduleSlot not found.'}, status=404)
        user = request.user
        # Only enrolled students or teacher can view
        if not (user == slot.teacher or slot.enrollments.filter(student=user).exists()):
            return Response({'detail': 'Not allowed.'}, status=403)
        news = ScheduleSlotNews.objects.filter(schedule_slot=slot).order_by('-created_at')
        return Response(ScheduleSlotNewsSerializer(news, many=True, context={'request': request}).data)

    
    @extend_schema(
        request={
            'multipart/form-data': inline_serializer(
                name='NewsFeedPostMultipartRequest',
                fields={
                    'scheduleslot': serializers.IntegerField(),
                    'type': serializers.ChoiceField(choices=['message', 'file', 'image']),
                    'title': serializers.CharField(required=False),
                    'content': serializers.CharField(required=False),
                    'file': serializers.FileField(required=False),
                    'image': serializers.ImageField(required=False),
                }
            ),
            'application/json': inline_serializer(
                name='NewsFeedPostJsonRequest',
                fields={
                    'scheduleslot': serializers.IntegerField(),
                    'type': serializers.ChoiceField(choices=['message', 'file', 'image']),
                    'title': serializers.CharField(required=False),
                    'content': serializers.CharField(required=False),
                    # Note: file/image can't be sent via JSON
                }
            )
        },
        responses=ScheduleSlotNewsSerializer,
        description="Post a new message/file/image to the news feed for a schedule slot. Only the assigned teacher can post. Files/images must be sent via multipart/form-data."
    )
    def post(self, request):
        slot_id = request.data.get('scheduleslot') or request.query_params.get('scheduleslot')
        if not slot_id:
            return Response({'detail': 'scheduleslot required.'}, status=400)
        
        try:
            slot = ScheduleSlot.objects.get(id=slot_id)
        except ScheduleSlot.DoesNotExist:
            return Response({'detail': 'ScheduleSlot not found.'}, status=404)
        
        user = request.user
        if not (hasattr(user, 'user_type') and user.user_type == 'teacher' and user == slot.teacher):
            return Response({'detail': 'Only the assigned teacher can post.'}, status=403)
        
        data = {}
        for key, value in request.data.items():
            if key not in ['file', 'image']:
                data[key] = value
        data['schedule_slot'] = slot.id
        data['author'] = user.id
        file_storage_obj = None
        if data.get('type') == 'file' and 'file' in request.FILES:
            file_obj = request.FILES['file']
            try:
                tg_result = upload_to_telegram(file_obj)
                file_storage_obj = FileStorage.objects.create(
                    file=file_obj,
                    telegram_file_id=tg_result['file_id'],
                    telegram_download_link=tg_result['download_link'],
                    uploaded_by=user
                )
            except Exception as e:
                return Response({'detail': f'Telegram upload failed: {str(e)}'}, status=500)
        if file_storage_obj:
            data['file_storage'] = file_storage_obj.id
        if 'file' in request.FILES and not file_storage_obj:
            data['file'] = request.FILES['file']
        if 'image' in request.FILES:
            data['image'] = request.FILES['image']
        serializer = ScheduleSlotNewsSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            instance = serializer.save()
            return Response(ScheduleSlotNewsSerializer(instance, context={'request': request}).data, status=201)
        return Response(serializer.errors, status=400)

class PrivateLessonRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PrivateLessonRequestSerializer
    queryset = PrivateLessonRequest.objects.select_related('student', 'schedule_slot')

    def get_permissions(self):
        if self.action in ['create','pick_option']:
            return [IsStudent()]
        if self.action in ['propose_option', 'confirm']:
            return [IsReception()]
        return [IsReceptionOrStudent()]

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if hasattr(user, 'user_type'):
            if user.user_type == 'student':
                return qs.filter(student=user)
            if user.user_type == 'reception':
                return qs
        return qs.none()

    @extend_schema(
        request=inline_serializer(
            name='ProposeOptionsRequest',
            fields={
                'options': serializers.ListField(
                    child=inline_serializer(
                        name='ProposedOption',
                        fields={
                            'date': serializers.DateField(),
                            'time_from': serializers.TimeField(),
                            'time_to': serializers.TimeField(),
                        }
                    )
                )
            }
        ),
        responses=PrivateLessonRequestSerializer,
        description="Reception proposes one or more alternative times."
    )
    @action(detail=True, methods=['post'], url_path='propose-option')
    def propose_option(self, request, pk=None):
        req = self.get_object()
        options = request.data.get('options', [])
        if not isinstance(options, list) or not options:
            return Response({'detail': 'options must be a non-empty list.'}, status=400)
        created = []
        for opt in options:
            serializer = PrivateLessonProposedOptionSerializer(data=opt)
            if serializer.is_valid():
                serializer.save(request=req)
                created.append(serializer.data)
            else:
                return Response(serializer.errors, status=400)
        req.status = 'proposed'
        req.save()
        return Response(self.get_serializer(req).data)

    @extend_schema(
        request=inline_serializer(
            name='PickOptionRequest',
            fields={
                'option_id': serializers.IntegerField()
            }
        ),
        responses=PrivateLessonRequestSerializer,
        description="Student picks a proposed option by id."
    )
    @action(detail=True, methods=['post'], url_path='pick-option')
    def pick_option(self, request, pk=None):
        req = self.get_object()
        if req.student != request.user:
            return Response({'detail': 'Not allowed.'}, status=403)
        option_id = request.data.get('option_id')
        try:
            option = req.proposed_options.get(id=option_id)
        except PrivateLessonProposedOption.DoesNotExist:
            return Response({'detail': 'Option not found.'}, status=404)
        req.confirmed_date = option.date
        req.confirmed_time_from = option.time_from
        req.confirmed_time_to = option.time_to
        req.status = 'confirmed'
        req.save()
        return Response(self.get_serializer(req).data)

    @extend_schema(
        request=None,
        responses=PrivateLessonRequestSerializer,
        description="Reception confirms the request (only id in path)."
    )
    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        req = self.get_object()
        # If not already set, use preferred values
        if not req.confirmed_date:
            req.confirmed_date = req.preferred_date
        if not req.confirmed_time_from:
            req.confirmed_time_from = req.preferred_time_from
        if not req.confirmed_time_to:
            req.confirmed_time_to = req.preferred_time_to
        req.status = 'confirmed'
        req.save()
        return Response(self.get_serializer(req).data)

    @extend_schema(
        request=None,
        responses=PrivateLessonRequestSerializer,
        description="Reception cancels the request (only id in path)."
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        req = self.get_object()
        req.status = 'cancelled'
        req.save()
        return Response(self.get_serializer(req).data)