import random
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiRequest
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from .models import *
from .serializers import *
from core.tasks import notify_exam_attempt_submitted, notify_exam_graded_task
from core.permissions import IsTeacherOrReceptionOrAdmin

def populate_attempt_questions(attempt):
    counts = attempt.exam.template.counts
    order = 1
    picked = []
    for diff, needed in counts.items():
        pool = list(
            QuestionBank.objects
            .filter(language=attempt.exam.language, difficulty=diff)
            .annotate(choice_count=models.Count('choices'))
            .filter(choice_count__gte=2)
            .order_by('?')[:needed]
        )
        picked.extend(pool)
    random.shuffle(picked)
    with transaction.atomic():
        for bank in picked:
            aq = AttemptQuestion.objects.create(
                attempt=attempt,
                bank_question=bank,
                text=bank.text,
                question_type=bank.question_type,
                points=bank.points,
                order=order,
            )
            order += 1
            for bc in bank.choices.all():
                AttemptChoice.objects.create(
                    attempt_question=aq,
                    text=bc.text,
                    is_correct=bc.is_correct,
                    order=bc.order,
                )

class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.filter(is_active=True)
    serializer_class = LanguageSerializer
    permission_classes = [permissions.IsAuthenticated]

class LanguageLevelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LanguageLevel.objects.all()
    serializer_class = LanguageLevelSerializer
    permission_classes = [permissions.IsAuthenticated]

class QuestionBankViewSet(viewsets.ModelViewSet):
    queryset = QuestionBank.objects.all().prefetch_related('choices')
    serializer_class = QuestionBankSerializer
    permission_classes = [IsTeacherOrReceptionOrAdmin]

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        ser = QuestionBankSerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)

class EntranceExamViewSet(viewsets.ModelViewSet):
    queryset = EntranceExam.objects.all().select_related('language', 'grading_teacher')
    filterset_fields = ['language', 'grading_teacher', 'is_active']
    search_fields = ['title', 'description']
    ordering = ['-created_at']

    def get_serializer_class(self):
        return EntranceExamSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTeacherOrReceptionOrAdmin()]
        return [permissions.IsAuthenticated()]
    
    @extend_schema(
        request=QRSerializer,
        responses={201: ExamAttemptSerializer}
    )
    @action(detail=False, methods=['post'])
    def start_by_qr(self, request):
        from rest_framework import serializers as rfserializers
        class QRSerializer(rfserializers.Serializer):
            qr_code = rfserializers.UUIDField()
        if not hasattr(request.user, 'profile'):
            return Response(
                {'error': 'Student profile is required before taking the entrance exam.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        ser = QRSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        exam = get_object_or_404(EntranceExam, qr_code=ser.validated_data['qr_code'], is_active=True)
        if request.user.user_type != 'student':
            return Response({'error': 'Only students can start exams'}, status=status.HTTP_403_FORBIDDEN)
        if ExamAttempt.objects.filter(exam=exam, student=request.user).exists():
            return Response({'error': 'Already attempted'}, status=status.HTTP_400_BAD_REQUEST)
        attempt = ExamAttempt.objects.create(exam=exam, student=request.user, status='mcq_in_progress')
        populate_attempt_questions(attempt)
        return Response(ExamAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

class ExamAttemptViewSet(viewsets.ModelViewSet):
    serializer_class = ExamAttemptSerializer
    filterset_fields = ['exam', 'student', 'status']
    ordering = ['-started_at']

    def get_permissions(self):
        if self.action == 'submit_mcq_bulk':
            return [permissions.IsAuthenticated()]
        if self.action == 'grade':
            return [IsTeacherOrReceptionOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = ExamAttempt.objects.select_related('exam', 'student', 'achieved_level')
        if user.user_type == 'student':
            qs = qs.filter(student=user)
        elif user.user_type == 'teacher':
            qs = qs.filter(exam__grading_teacher=user)
        return qs

    def get_serializer_class(self):
        return ExamAttemptDetailSerializer if self.action == 'retrieve' else ExamAttemptSerializer
    
    @extend_schema(
        request=MCQBulkSubmitSerializer,
        responses={200: ExamAttemptSerializer}
    )
    @action(detail=True, methods=['post'])
    @action(detail=True, methods=['post'])
    def submit_mcq_bulk(self, request, pk=None):
        attempt = self.get_object()
        if attempt.student != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        if attempt.status != 'mcq_in_progress':
            return Response({'error': 'MCQ not in progress'}, status=status.HTTP_400_BAD_REQUEST)

        ser = MCQBulkSubmitSerializer(data=request.data, context={'attempt': attempt})
        ser.is_valid(raise_exception=True)

        with transaction.atomic():
            for ans in ser.validated_data['answers']:
                aq = AttemptQuestion.objects.get(id=ans['question'])
                choice_obj = aq.choices.get(order=ans['choice_index'] - 1)
                answer, _ = AttemptAnswer.objects.get_or_create(
                    attempt=attempt, attempt_question=aq)
                answer.selected_choice = choice_obj
                answer.calculate_points()

            attempt.mcq_score = sum(a.points_earned for a in attempt.answers.all())
            attempt.mcq_completed_at = timezone.now()
            attempt.status = 'mcq_completed'
            attempt.save()
            
            notify_exam_attempt_submitted.delay(attempt.id)

        return Response(ExamAttemptSerializer(attempt).data)
    
    @extend_schema(
        request=TeacherGradeSerializer,
        responses={200: ExamAttemptSerializer}
    )
    @action(detail=True, methods=['post'])
    def grade(self, request, pk=None):
        """Teacher submits speaking & writing scores and marks exam graded."""
        attempt = self.get_object()
        user = request.user
        if user.user_type != 'teacher' or attempt.exam.grading_teacher != user:
            return Response({'error': 'Not authorised'}, status=status.HTTP_403_FORBIDDEN)

        ser = TeacherGradeSerializer(data=request.data, context={'attempt': attempt})
        ser.is_valid(raise_exception=True)

        attempt.speaking_score = ser.validated_data['speaking_score']
        attempt.writing_score  = ser.validated_data['writing_score']
        attempt.status = 'graded'
        attempt.graded_at = timezone.now()
        attempt.calculate_final_score()
        notify_exam_graded_task.delay(attempt.id)

        return Response(ExamAttemptSerializer(attempt).data)