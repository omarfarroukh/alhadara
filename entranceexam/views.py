from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import (
    Language, LanguageLevel, EntranceExam, ExamQuestion,
    ExamChoice, ExamAttempt, ExamAnswer
)
from .serializers import (
    LanguageSerializer, LanguageLevelSerializer, EntranceExamSerializer,
    EntranceExamDetailSerializer, EntranceExamCreateSerializer,
    ExamQuestionSerializer, ExamQuestionCreateSerializer,
    ExamAttemptSerializer, ExamAttemptDetailSerializer,
    ExamAnswerSerializer, ExamAnswerSubmitSerializer,
    ExamStartSerializer, ExamSubmitSerializer, ExamGradingSerializer,
    StudentResultSerializer
)
from core.permissions import IsTeacherOrReceptionOrAdmin

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for managing languages"""
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated]

class LanguageLevelViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing language levels"""
    queryset = LanguageLevel.objects.all()
    serializer_class = LanguageLevelSerializer
    permission_classes = [permissions.IsAuthenticated]

class EntranceExamViewSet(viewsets.ModelViewSet):
    """ViewSet for managing entrance exams"""
    queryset = EntranceExam.objects.all().select_related('language', 'grading_teacher')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['language', 'grading_teacher', 'is_active']
    search_fields = ['title', 'description', 'language__name']
    ordering_fields = ['title', 'created_at', 'language']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return EntranceExamCreateSerializer
        elif self.action == 'retrieve':
            return EntranceExamDetailSerializer
        return EntranceExamSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrReceptionOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Teachers can only see exams they are assigned to grade
        if user.user_type == 'teacher':
            queryset = queryset.filter(grading_teacher=user)
        
        return queryset.prefetch_related('questions__choices')
    
    @extend_schema(
        request=ExamStartSerializer,
        responses={201: ExamAttemptSerializer}
    )
    @action(detail=False, methods=['post'])
    def start_by_qr(self, request):
        """Start exam attempt using QR code"""
        serializer = ExamStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        qr_code = serializer.validated_data['qr_code']
        user = request.user
        
        # Check if user is a student
        if user.user_type != 'student':
            return Response(
                {'error': 'Only students can take entrance exams'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        if not hasattr(request.user, 'profile'):
            return Response(
                {'error': 'Student profile is required before taking the entrance exam.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Get the exam
        exam = get_object_or_404(EntranceExam, qr_code=qr_code, is_active=True)
        
        # Check if student already has an attempt for this exam
        existing_attempt = ExamAttempt.objects.filter(
            exam=exam,
            student=user
        ).first()
        
        if existing_attempt:
            return Response(
                {'error': 'You have already attempted this exam'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create new attempt
        attempt = ExamAttempt.objects.create(
            exam=exam,
            student=user,
            status='mcq_in_progress'
        )
        
        return Response(
            ExamAttemptSerializer(attempt).data,
            status=status.HTTP_201_CREATED
        )
    
    @extend_schema(
        responses={200: ExamAttemptDetailSerializer}
    )
    @action(detail=True, methods=['get'])
    def current_attempt(self, request, pk=None):
        """Get current user's attempt for this exam"""
        exam = self.get_object()
        user = request.user
        
        if user.user_type != 'student':
            return Response(
                {'error': 'Only students can have exam attempts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            attempt = ExamAttempt.objects.get(exam=exam, student=user)
            return Response(ExamAttemptDetailSerializer(attempt).data)
        except ExamAttempt.DoesNotExist:
            return Response(
                {'error': 'No attempt found for this exam'},
                status=status.HTTP_404_NOT_FOUND
            )

class ExamQuestionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exam questions"""
    serializer_class = ExamQuestionSerializer
    permission_classes = [IsTeacherOrReceptionOrAdmin]
    
    def get_queryset(self):
        exam_id = self.kwargs.get('exam_pk')
        if exam_id:
            return ExamQuestion.objects.filter(exam_id=exam_id).prefetch_related('choices')
        return ExamQuestion.objects.none()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExamQuestionCreateSerializer
        return ExamQuestionSerializer
    
    def perform_create(self, serializer):
        exam_id = self.kwargs.get('exam_pk')
        exam = get_object_or_404(EntranceExam, id=exam_id)
        serializer.save(exam=exam)

class ExamAttemptViewSet(viewsets.ModelViewSet):
    """ViewSet for managing exam attempts"""
    serializer_class = ExamAttemptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['exam', 'student', 'status']
    search_fields = ['student__first_name', 'student__last_name', 'exam__title']
    ordering_fields = ['started_at', 'status', 'percentage']
    ordering = ['-started_at']
    
    def get_permissions(self):
        if self.action in ['submit_mcq', 'answer_question']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['grade_attempt']:
            return [IsTeacherOrReceptionOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        queryset = ExamAttempt.objects.select_related(
            'exam', 'student', 'achieved_level'
        ).prefetch_related('answers__selected_choices')
        
        # Students can only see their own attempts
        if user.user_type == 'student':
            queryset = queryset.filter(student=user)
        # Teachers can only see attempts for exams they grade
        elif user.user_type == 'teacher':
            queryset = queryset.filter(exam__grading_teacher=user)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamAttemptDetailSerializer
        elif self.action == 'grade_attempt':
            return ExamGradingSerializer
        return ExamAttemptSerializer
    
    @extend_schema(
        request=ExamAnswerSubmitSerializer,
        responses={200: ExamAnswerSerializer}
    )
    @action(detail=True, methods=['post'])
    def answer_question(self, request, pk=None):
        """Submit answer for a specific question"""
        attempt = self.get_object()
        user = request.user
        
        # Check if user is the student who owns this attempt
        if attempt.student != user:
            return Response(
                {'error': 'You can only answer questions for your own attempt'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if MCQ section is still in progress
        if not attempt.can_student_access_mcq():
            return Response(
                {'error': 'MCQ section is not accessible'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if time has expired
        if attempt.auto_submit_mcq_if_expired():
            return Response(
                {'error': 'Time has expired. MCQ section automatically submitted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ExamAnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        question = serializer.validated_data['question']
        selected_choices = serializer.validated_data['selected_choices']
        
        # Verify question belongs to this exam
        if question.exam != attempt.exam:
            return Response(
                {'error': 'Question does not belong to this exam'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or update answer
        answer, created = ExamAnswer.objects.get_or_create(
            attempt=attempt,
            question=question,
            defaults={'points_earned': 0}
        )
        
        # Clear existing choices and set new ones
        answer.selected_choices.clear()
        answer.selected_choices.set(selected_choices)
        
        # Calculate points
        answer.calculate_points()
        
        return Response(ExamAnswerSerializer(answer).data)
    
    @extend_schema(
        request=ExamSubmitSerializer,
        responses={200: ExamAttemptSerializer}
    )
    @action(detail=True, methods=['post'])
    def submit_mcq(self, request, pk=None):
        """Submit MCQ section"""
        attempt = self.get_object()
        user = request.user
        
        # Check if user is the student who owns this attempt
        if attempt.student != user:
            return Response(
                {'error': 'You can only submit your own attempt'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if MCQ section is still in progress
        if not attempt.can_student_access_mcq():
            return Response(
                {'error': 'MCQ section is not in progress'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate MCQ score
        mcq_score = sum(answer.points_earned for answer in attempt.answers.all())
        
        # Update attempt
        attempt.mcq_score = mcq_score
        attempt.mcq_completed_at = timezone.now()
        attempt.status = 'mcq_completed'
        attempt.save()
        
        return Response(ExamAttemptSerializer(attempt).data)
    
    @extend_schema(
        request=ExamGradingSerializer,
        responses={200: ExamAttemptSerializer}
    )
    @action(detail=True, methods=['patch'])
    def grade_attempt(self, request, pk=None):
        """Grade speaking/writing sections and finalize exam"""
        attempt = self.get_object()
        user = request.user
        
        # Check if user is the grading teacher
        if attempt.exam.grading_teacher != user:
            return Response(
                {'error': 'You are not authorized to grade this exam'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ExamGradingSerializer(attempt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Save the grading
        serializer.save()
        
        # If this completes the grading, calculate final results
        if attempt.status == 'graded':
            attempt.calculate_final_score()
            attempt.graded_at = timezone.now()
            attempt.save()
            
            # Update student's profile with achieved language level
            if attempt.achieved_level:
                try:
                    profile = attempt.student.profile
                    profile.update_language_level(
                        attempt.exam.language.name,
                        attempt.achieved_level
                    )
                except AttributeError:
                    pass  # Profile doesn't exist
        
        return Response(ExamAttemptSerializer(attempt).data)
    
    @extend_schema(
        responses={200: StudentResultSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def my_results(self, request):
        """Get current user's exam results"""
        user = request.user
        
        if user.user_type != 'student':
            return Response(
                {'error': 'Only students can view exam results'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        attempts = ExamAttempt.objects.filter(
            student=user,
            status='graded'
        ).select_related('exam__language', 'achieved_level')
        
        return Response(StudentResultSerializer(attempts, many=True).data)

class ExamAnswerViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing exam answers"""
    serializer_class = ExamAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        attempt_id = self.kwargs.get('attempt_pk')
        
        if not attempt_id:
            return ExamAnswer.objects.none()
        
        queryset = ExamAnswer.objects.filter(attempt_id=attempt_id).select_related(
            'question', 'attempt__student'
        ).prefetch_related('selected_choices')
        
        # Students can only see their own answers
        if user.user_type == 'student':
            queryset = queryset.filter(attempt__student=user)
        # Teachers can only see answers for exams they grade
        elif user.user_type == 'teacher':
            queryset = queryset.filter(attempt__exam__grading_teacher=user)
        
        return queryset
