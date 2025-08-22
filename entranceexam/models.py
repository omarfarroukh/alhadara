from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid
from io import BytesIO
import base64
import qrcode

User = get_user_model()

class Language(models.Model):
    LANGUAGE_CHOICES = [('english', 'English'), ('german', 'German'), ('french', 'French'), ('spanish', 'Spanish')]
    name = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return dict(self.LANGUAGE_CHOICES)[self.name]

class LanguageLevel(models.Model):
    LEVEL_CHOICES = [('a1', 'A1 – Beginner'), ('a2', 'A2 – Elementary'), ('b1', 'B1 – Intermediate'),
                     ('b2', 'B2 – Upper Intermediate'), ('c1', 'C1 – Advanced'), ('c2', 'C2 – Proficiency')]
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, unique=True)
    min_score = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    max_score = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])

    def clean(self):
        if self.min_score >= self.max_score:
            raise ValidationError("min_score must be < max_score")

    def __str__(self):
        return dict(self.LEVEL_CHOICES)[self.level]

class EntranceExam(models.Model):
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    grading_teacher = models.ForeignKey(
        User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'teacher'})
    mcq_time_limit_minutes = models.PositiveIntegerField(default=60)
    mcq_total_points = models.PositiveIntegerField(default=100)
    speaking_total_points = models.PositiveIntegerField(default=100)
    writing_total_points = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def qr_image_base64(self):
        qr = qrcode.make(str(self.qr_code))
        buf = BytesIO()
        qr.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    def __str__(self):
        return f"{self.language} – {self.title}"

    def get_total_points(self):
        return self.mcq_total_points + self.speaking_total_points + self.writing_total_points

    def calculate_percentage(self, earned):
        total = self.get_total_points()
        return (earned / total) * 100 if total else 0

    def get_level_for_score(self, pct):
        return LanguageLevel.objects.filter(min_score__lte=pct, max_score__gte=pct).first()

class ExamTemplate(models.Model):
    exam = models.OneToOneField(EntranceExam, on_delete=models.CASCADE, related_name='template')
    counts = models.JSONField(default=dict)  # {"easy": 5, "medium": 3, "hard": 2}

    def __str__(self):
        return f"Template for {self.exam.title}"

# ---------- Question Bank ----------
class QuestionBank(models.Model):
    DIFFICULTIES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='question_banks')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=[('multiple_choice', 'Multiple Choice'),
                                                             ('true_false', 'True/False')])
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    points = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(50)])
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.choices.filter(is_correct=True).count() != 1:
            raise ValidationError("Exactly one choice must be marked correct.")

    def __str__(self):
        return f"{self.language} {self.difficulty}: {self.text[:40]}..."

class QuestionBankChoice(models.Model):
    question = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

# ---------- Runtime Attempt Tables ----------
class ExamAttempt(models.Model):
    STATUS = [
        ('mcq_in_progress', 'MCQ Section In Progress'),
        ('mcq_completed', 'MCQ Section Completed'),
        ('graded', 'Graded'),
    ]
    exam = models.ForeignKey(EntranceExam, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'student'})
    started_at = models.DateTimeField(auto_now_add=True)
    mcq_completed_at = models.DateTimeField(null=True, blank=True)
    speaking_completed_at = models.DateTimeField(null=True, blank=True)
    writing_completed_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='mcq_in_progress')
    mcq_score = models.PositiveIntegerField(default=0)
    speaking_score = models.PositiveIntegerField(default=0)
    writing_score = models.PositiveIntegerField(default=0)
    total_score = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    achieved_level = models.ForeignKey(LanguageLevel, on_delete=models.SET_NULL, null=True, blank=True)
    speaking_notes = models.TextField(blank=True)
    writing_notes = models.TextField(blank=True)
    general_feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('exam', 'student')
        ordering = ['-started_at']

    def get_time_remaining_mcq(self):
        from datetime import timedelta
        if self.status != 'mcq_in_progress':
            return None
        elapsed = timezone.now() - self.started_at
        remaining = timedelta(minutes=self.exam.mcq_time_limit_minutes) - elapsed
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def can_student_access_mcq(self):
        return self.status == 'mcq_in_progress'
    
    def calculate_final_score(self):
        self.total_score = self.mcq_score + self.speaking_score + self.writing_score
        self.percentage = Decimal(str(self.exam.calculate_percentage(self.total_score))).quantize(Decimal('0.01'))
        self.achieved_level = self.exam.get_level_for_score(float(self.percentage))
        self.save()

class AttemptQuestion(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='questions')
    bank_question = models.ForeignKey(QuestionBank, on_delete=models.CASCADE)
    text = models.TextField()
    question_type = models.CharField(max_length=20)
    points = models.PositiveIntegerField()
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

    def clean(self):
        if self.choices.filter(is_correct=True).count() != 1:
            raise ValidationError("Exactly one choice must be marked correct.")

    def get_correct_choice(self):
        return self.choices.get(is_correct=True)

class AttemptChoice(models.Model):
    attempt_question = models.ForeignKey(AttemptQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    attempt_question = models.ForeignKey(AttemptQuestion, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(AttemptChoice, on_delete=models.CASCADE, null=True, blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('attempt', 'attempt_question')

    def calculate_points(self):
        correct_choice = self.attempt_question.get_correct_choice()
        self.is_correct = self.selected_choice == correct_choice
        self.points_earned = self.attempt_question.points if self.is_correct else 0
        self.save()
        return self.points_earned