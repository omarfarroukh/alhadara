from rest_framework import viewsets, permissions, status, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse,inline_serializer,OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Quiz, Question, Choice, QuizAttempt, QuizAnswer
from .serializers import (
    QuizBulkSubmitSerializer, QuizSerializer, QuizDetailSerializer, QuizCreateSerializer,
    QuestionCreateSerializer, QuizAttemptSerializer, QuizAnswerSerializer,
    QuizAnswerSubmitSerializer, QuizStartSerializer, QuizSubmitSerializer,
    QuizResultSerializer
)
from core.permissions import IsTeacherOrReceptionOrAdmin

class QuizViewSet(viewsets.ModelViewSet):
    """ViewSet for managing quizzes"""
    queryset = Quiz.objects.all().select_related('course', 'schedule_slot')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['course', 'schedule_slot', 'is_active']
    search_fields = ['title', 'description', 'course__title']
    ordering_fields = ['title', 'created_at', 'passing_score']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return QuizCreateSerializer
        elif self.action == 'retrieve':
            return QuizDetailSerializer
        return QuizSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrReceptionOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Students can only see quizzes for courses they're enrolled in
        if user.user_type == 'student':
            enrolled_course_ids = user.enrollments.filter(
                status__in=['pending', 'active']
            ).values_list('course_id', flat=True)
            queryset = queryset.filter(course_id__in=enrolled_course_ids)
        
        # Teachers can only see quizzes for courses they teach
        elif user.user_type == 'teacher':
            teaching_slot_ids = user.teaching_slots.values_list('course_id', flat=True)
            queryset = queryset.filter(course_id__in=teaching_slot_ids)
        
        return queryset.prefetch_related('questions', 'attempts')
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='course_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter quizzes by course ID',
                required=False
            ),
            OpenApiParameter(
                name='schedule_slot_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter quizzes by schedule slot ID',
                required=False
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        request=QuizStartSerializer,
        responses={201: QuizAttemptSerializer}
    )
    @action(detail=True, methods=['post'])
    def start_attempt(self, request, pk=None):
        """Start a new quiz attempt"""
        quiz = self.get_object()
        user = request.user
        
        # Check if quiz is available
        is_available, message = quiz.is_available_for_user(user)
        if not is_available:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new attempt
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=user,
            status='in_progress'
        )
        
        serializer = QuizAttemptSerializer(attempt, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        request=QuizSubmitSerializer,
        responses={200: QuizResultSerializer}
    )
    @action(detail=True, methods=['post'])
    def submit_attempt(self, request, pk=None):
        """Submit a completed quiz attempt"""
        quiz = self.get_object()
        attempt_id = request.data.get('attempt_id')
        
        try:
            attempt = QuizAttempt.objects.get(
                id=attempt_id,
                quiz=quiz,
                user=request.user,
                status='in_progress'
            )
        except QuizAttempt.DoesNotExist:
            return Response(
                {'error': 'Invalid attempt or attempt already submitted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Complete the attempt
        attempt.status = 'completed'
        attempt.completed_at = timezone.now()
        attempt.calculate_score()
        attempt.save()
        
        serializer = QuizResultSerializer(attempt, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def my_attempts(self, request, pk=None):
        """Get user's attempts for this quiz"""
        quiz = self.get_object()
        attempts = quiz.attempts.filter(user=request.user).order_by('-started_at')
        serializer = QuizAttemptSerializer(attempts, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get quiz statistics (for teachers/admins)"""
        quiz = self.get_object()
        
        # Check permissions
        if request.user.user_type == 'student':
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        attempts = quiz.attempts.filter(status='completed')
        
        stats = {
            'total_attempts': attempts.count(),
            'unique_students': attempts.values('user').distinct().count(),
            'average_score': attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0,
            'pass_rate': 0,
            'score_distribution': {
                '0-50': attempts.filter(score__lte=50).count(),
                '51-70': attempts.filter(score__gt=50, score__lte=70).count(),
                '71-85': attempts.filter(score__gt=70, score__lte=85).count(),
                '86-100': attempts.filter(score__gt=85).count(),
            }
        }
        
        if stats['total_attempts'] > 0:
            passed_attempts = attempts.filter(passed=True).count()
            stats['pass_rate'] = (passed_attempts / stats['total_attempts']) * 100
        
        return Response(stats)

    @extend_schema(
        responses={200: {
            'type': 'object',
            'properties': {
                'quiz_id': {'type': 'integer'},
                'quiz_title': {'type': 'string'},
                'time_limit_minutes': {'type': 'integer'},
                'questions': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'order': {'type': 'integer'},
                            'text': {'type': 'string'},
                            'question_type': {'type': 'string'},
                            'points': {'type': 'integer'},
                            'choices': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'order': {'type': 'integer'},
                                        'text': {'type': 'string'}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }}
    )
    @action(detail=True, methods=['get'])
    def questions_for_student(self, request, pk=None):
        """Get quiz questions with order numbers for students"""
        quiz = self.get_object()
        
        # Check if user is enrolled in the course
        if not request.user.enrollments.filter(
            course=quiz.course,
            status__in=['pending', 'active']
        ).exists():
            return Response(
                {'error': 'You must be enrolled in this course to take the quiz'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get questions with choices, ordered by question order
        questions = quiz.questions.all().prefetch_related('choices').order_by('order')
        
        questions_data = []
        for question in questions:
            question_data = {
                'order': question.order,
                'text': question.text,
                'question_type': question.question_type,
                'points': question.points,
                'choices': []
            }
            
            # Add choices with order numbers (but hide correct answers)
            for choice in question.choices.all().order_by('order'):
                question_data['choices'].append({
                    'order': choice.order,
                    'text': choice.text
                })
            
            questions_data.append(question_data)
        
        response_data = {
            'quiz_id': quiz.id,
            'quiz_title': quiz.title,
            'time_limit_minutes': quiz.time_limit_minutes,
            'questions': questions_data
        }
        
        return Response(response_data)

class QuestionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing quiz questions"""
    queryset = Question.objects.all().select_related('quiz')
    serializer_class = QuestionCreateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quiz', 'question_type']
    
    def get_permissions(self):
        return [IsTeacherOrReceptionOrAdmin()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Teachers can only manage questions for quizzes they teach
        if user.user_type == 'teacher':
            teaching_slot_ids = user.teaching_slots.values_list('course_id', flat=True)
            queryset = queryset.filter(quiz__course_id__in=teaching_slot_ids)
        
        return queryset.prefetch_related('choices')

class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing quiz attempts"""
    serializer_class = QuizAttemptSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['quiz', 'status', 'passed']
    ordering_fields = ['started_at', 'completed_at', 'score']
    ordering = ['-started_at']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'student':
            # Students can only see their own attempts
            return QuizAttempt.objects.filter(user=user).select_related('quiz')
        elif user.user_type == 'teacher':
            # Teachers can see attempts for quizzes they teach
            teaching_slot_ids = user.teaching_slots.values_list('course_id', flat=True)
            return QuizAttempt.objects.filter(
                quiz__course_id__in=teaching_slot_ids
            ).select_related('quiz', 'user')
        else:
            # Admins/reception can see all attempts
            return QuizAttempt.objects.all().select_related('quiz', 'user')
    
    @extend_schema(
        responses={200: QuizResultSerializer}
    )
    @action(detail=True, methods=['get'])
    def result(self, request, pk=None):
        """Get detailed result for a quiz attempt"""
        attempt = self.get_object()
        
        # Check permissions
        if request.user.user_type == 'student' and attempt.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = QuizResultSerializer(attempt, context={'request': request})
        return Response(serializer.data)

class QuizAnswerViewSet(viewsets.ModelViewSet):
    """ViewSet for managing quiz answers"""
    queryset = QuizAnswer.objects.all().select_related('attempt', 'question')
    serializer_class = QuizAnswerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['attempt', 'question', 'is_correct']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return QuizAnswerSubmitSerializer
        elif self.action == 'bulk_submit':
            return QuizBulkSubmitSerializer
        return QuizAnswerSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'bulk_submit']:
            return [permissions.IsAuthenticated()]
        return [IsTeacherOrReceptionOrAdmin()]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_type == 'student':
            # Students can only see their own answers
            return QuizAnswer.objects.filter(attempt__user=user).select_related(
                'attempt', 'question'
            ).prefetch_related('selected_choices')
        elif user.user_type == 'teacher':
            # Teachers can see answers for quizzes they teach
            teaching_slot_ids = user.teaching_slots.values_list('course_id', flat=True)
            return QuizAnswer.objects.filter(
                attempt__quiz__course_id__in=teaching_slot_ids
            ).select_related('attempt', 'question', 'attempt__user').prefetch_related('selected_choices')
        else:
            # Admins/reception can see all answers
            return QuizAnswer.objects.all().select_related(
                'attempt', 'question', 'attempt__user'
            ).prefetch_related('selected_choices')
    
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'points_earned': {'type': 'integer'},
                    'is_correct': {'type': 'boolean'}
                }
            }
        },
        responses={200: QuizAnswerSerializer}
    )
    @action(detail=True, methods=['post'])
    def grade(self, request, pk=None):
        """Grade a manually graded answer (for teachers/admins)"""
        answer = self.get_object()
        
        # Check permissions
        if request.user.user_type == 'student':
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        points_earned = request.data.get('points_earned', 0)
        is_correct = request.data.get('is_correct', False)
        
        answer.points_earned = points_earned
        answer.is_correct = is_correct
        answer.save()
        
        # Recalculate attempt score
        attempt = answer.attempt
        attempt.calculate_score()
        
        serializer = QuizAnswerSerializer(answer, context={'request': request})
        return Response(serializer.data)
    
    @extend_schema(
        request=QuizBulkSubmitSerializer,
        responses={201: QuizAnswerSerializer(many=True)},
        description="Submit multiple quiz answers in bulk"
    )
    @action(detail=False, methods=['post'], url_path='bulk-submit')
    def bulk_submit(self, request):
        """Handle bulk submission of quiz answers"""
        serializer = QuizBulkSubmitSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        attempt_id = serializer.validated_data['attempt_id']
        answers_data = serializer.validated_data['answers']

        # Prefetch attempt and question map
        attempt = QuizAttempt.objects.select_related('quiz').prefetch_related(
            'quiz__questions',
            'quiz__questions__choices'
        ).get(id=attempt_id)
        question_map = {q.order: q for q in attempt.quiz.questions.all()}

        created_answers = []
        errors = []

        for answer_data in answers_data:
            question_order = answer_data['question_order']
            question = question_map.get(question_order)
            choice_orders = answer_data.get('choice_orders', [])
            text_answer = answer_data.get('text_answer', '')

            answer_serializer = QuizAnswerSubmitSerializer(
                data={
                    'attempt_id': attempt_id,
                    'question_order': question_order,
                    'choice_orders': choice_orders,
                    'text_answer': text_answer
                },
                context={
                    'request': request,
                    '_attempt': attempt,
                    '_question': question
                }
            )

            if answer_serializer.is_valid():
                answer = answer_serializer.save()
                created_answers.append(answer)
            else:
                errors.append({
                    'question_order': question_order,
                    'errors': answer_serializer.errors
                })

        if errors:
            return Response({'errors': errors}, status=status.HTTP_207_MULTI_STATUS)

        # Finalize the attempt
        attempt.status = 'completed'
        attempt.calculate_score()
        attempt.save()

        return Response(
            QuizAnswerSerializer(created_answers, many=True).data,
            status=status.HTTP_201_CREATED
        )
