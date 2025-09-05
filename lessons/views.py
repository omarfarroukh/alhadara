from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tasks import notify_scheduleslot_news_task
from .models import Lesson, Homework, Attendance, HomeworkGrade
from .serializers import HomeworkCreateUpdateSerializer, LessonCreateUpdateSerializer, LessonSerializer, HomeworkSerializer, AttendanceSerializer, LessonSummarySerializer, HomeworkGradeSerializer, ScheduleSlotNewsCreateUpdateSerializer
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


LANG_PARAM = OpenApiParameter(
    name='lang',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description='Language code to translate translatable fields (en, ar)',
    required=False,
    enum=['en', 'ar']  
)

class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy','bulk']:
            return [IsTeacher()]
        return [permissions.IsAuthenticated()]
    
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LessonCreateUpdateSerializer
        return LessonSerializer
    
    @extend_schema(
        parameters=[
            LANG_PARAM,
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

    @extend_schema(parameters=[LANG_PARAM])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
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
            LANG_PARAM,
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
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return HomeworkCreateUpdateSerializer
        return HomeworkSerializer
    
    @extend_schema(
        parameters=[
            LANG_PARAM,
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
    
    @extend_schema(parameters=[LANG_PARAM])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
                                
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

class ScheduleSlotNewsViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for creating, reading, updating, and deleting news items
    for a specific schedule slot.
    """
    queryset = ScheduleSlotNews.objects.all().select_related(
        'author', 'schedule_slot', 'file_storage'
    ).order_by('-created_at')
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        """
        Use the CreateUpdate serializer for write actions and the detailed
        read serializer for read actions.
        """
        if self.action in ['create', 'update', 'partial_update']:
            return ScheduleSlotNewsCreateUpdateSerializer
        return ScheduleSlotNewsSerializer # For list, retrieve

    def get_permissions(self):
        """
        - Any enrolled student or the teacher can read news.
        - Only the author (who must be the teacher) can create, update, or delete.
        """
        if self.action in ['create']:
            return [IsTeacher()]
        if self.action in ['update', 'partial_update', 'destroy']:
            # For editing, you must be the author of the post.
            return [permissions.IsAuthenticated()] # We'll add a check inside the method
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """
        Filter the news items based on the 'schedule_slot' query parameter.
        Ensures the user has permission to view the feed for that slot.
        """
        qs = super().get_queryset()
        schedule_slot_id = self.request.query_params.get('schedule_slot')
        
        if not schedule_slot_id:
            # If no slot is specified, return nothing.
            return qs.none()

        try:
            slot = ScheduleSlot.objects.get(pk=schedule_slot_id)
            user = self.request.user
            
            # Check if user is the teacher or is enrolled
            is_enrolled = slot.enrollments.filter(student=user).exists()
            is_teacher = (user == slot.teacher)

            if not (is_enrolled or is_teacher):
                return qs.none() # User is not allowed to see this feed

            return qs.filter(schedule_slot_id=schedule_slot_id)
        except ScheduleSlot.DoesNotExist:
            return qs.none()
    # --- THIS IS THE CHANGE ---
    @extend_schema(
        summary="Create a new news item",
        description="Create a news post for a schedule slot. Use `multipart/form-data` to include an image or file upload.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'schedule_slot': {'type': 'integer', 'description': 'ID of the target schedule slot.'},
                    'type': {'type': 'string', 'enum': ['homework', 'quiz', 'message', 'file', 'image']},
                    'title': {'type': 'string', 'description': 'Title of the news post.'},
                    'content': {'type': 'string', 'description': 'Main text content of the post.'},
                    'image': {'type': 'string', 'format': 'binary', 'description': 'Upload an image file.'},
                    'file': {'type': 'string', 'format': 'binary', 'description': 'Upload a document (PDF, etc.) if type is "file".'},
                    'related_homework': {'type': 'integer', 'description': 'Link to a homework item.'},
                    'related_quiz': {'type': 'integer', 'description': 'Link to a quiz.'},
                },
                'required': ['schedule_slot', 'type']
            }
        },
        responses={201: ScheduleSlotNewsSerializer}
    )
    def create(self, request, *args, **kwargs):
        """This method now has explicit Swagger documentation for file uploads."""
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """
        Set the author and handle file uploads during creation.
        """
        user = self.request.user
        slot = serializer.validated_data['schedule_slot']

        # Security check: ensure the creator is the teacher of the target slot
        if user != slot.teacher:
            raise serializers.ValidationError("You can only post news to your own schedule slots.")

        # Handle file upload via Telegram
        file_obj = self.request.FILES.get('file')
        file_storage_instance = None
        if file_obj:
            try:
                tg_result = upload_to_telegram(file_obj)
                file_storage_instance = FileStorage.objects.create(
                    file=file_obj,
                    telegram_file_id=tg_result['file_id'],
                    telegram_download_link=tg_result['download_link'],
                    uploaded_by=user
                )
            except Exception as e:
                raise serializers.ValidationError({"file": f"Telegram upload failed: {str(e)}"})

        # Save the instance with the author and file_storage
        serializer.save(author=user, file_storage=file_storage_instance)
        
        notify_scheduleslot_news_task.delay(serializer.instance.id)


    def update(self, request, *args, **kwargs):
        """
        Handle updates, including permissions check for authorship.
        """
        instance = self.get_object()
        user = request.user

        # Security Check: Only the original author can edit
        if instance.author != user:
            return Response(
                {'detail': 'You do not have permission to edit this post.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Note: File update logic can be added here if needed
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Handle deletion, including permissions check for authorship.
        """
        instance = self.get_object()
        user = request.user

        # Security Check: Only the original author can delete
        if instance.author != user:
            return Response(
                {'detail': 'You do not have permission to delete this post.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Note: Deleting the FileStorage object could be added here if desired
        return super().destroy(request, *args, **kwargs)

    # Add Swagger documentation to the list action
    @extend_schema(
        parameters=[
            LANG_PARAM,
            OpenApiParameter(
                name='schedule_slot',
                description='The ID of the schedule slot to fetch news for.',
                required=True,
                type=OpenApiTypes.INT,
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists() and not self.request.query_params.get('schedule_slot'):
             return Response({"detail": "schedule_slot query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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