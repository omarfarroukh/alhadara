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
    """Languages available for entrance exams"""
    LANGUAGE_CHOICES = [
        ('english', 'English'),
        ('german', 'German'),
        ('french', 'French'),
        ('spanish', 'Spanish'),
    ]
    
    name = models.CharField(max_length=50, choices=LANGUAGE_CHOICES, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return dict(self.LANGUAGE_CHOICES)[self.name]

class LanguageLevel(models.Model):
    """Language proficiency levels"""
    LEVEL_CHOICES = [
        ('a1', 'A1 - Beginner'),
        ('a2', 'A2 - Elementary'),
        ('b1', 'B1 - Intermediate'),
        ('b2', 'B2 - Upper Intermediate'),
        ('c1', 'C1 - Advanced'),
        ('c2', 'C2 - Proficiency'),
    ]
    
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, unique=True)
    min_score = models.PositiveIntegerField(
        help_text="Minimum percentage score required for this level",
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    max_score = models.PositiveIntegerField(
        help_text="Maximum percentage score for this level",
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    class Meta:
        ordering = ['min_score']
    
    def __str__(self):
        return dict(self.LEVEL_CHOICES)[self.level]
    
    def clean(self):
        if self.min_score >= self.max_score:
            raise ValidationError("Minimum score must be less than maximum score")

class EntranceExam(models.Model):
    """Language entrance exam"""
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    grading_teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='grading_exams',
        limit_choices_to={'user_type': 'teacher'}
    )
    
    # Exam settings
    mcq_time_limit_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Time limit for MCQ/TF section in minutes"
    )
    mcq_total_points = models.PositiveIntegerField(
        default=100,
        help_text="Total points for MCQ/TF section"
    )
    speaking_total_points = models.PositiveIntegerField(
        default=100,
        help_text="Total points for speaking section"
    )
    writing_total_points = models.PositiveIntegerField(
        default=100,
        help_text="Total points for writing section"
    )
    
    is_active = models.BooleanField(default=True)
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    @property
    def qr_image_base64(self):
        """Return PNG QR as base64 data-URI."""
        qr = qrcode.make(str(self.qr_code))
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    
    def __str__(self):
        return f"{self.language} - {self.title}"
    
    def get_total_points(self):
        """Get total possible points for the exam"""
        return self.mcq_total_points + self.speaking_total_points + self.writing_total_points
    
    def calculate_percentage(self, earned_points):
        """Calculate percentage score from earned points"""
        total = self.get_total_points()
        if total == 0:
            return 0
        return (earned_points / total) * 100
    
    def get_level_for_score(self, percentage):
        """Get language level based on percentage score"""
        try:
            return LanguageLevel.objects.filter(
                min_score__lte=percentage,
                max_score__gte=percentage
            ).first()
        except LanguageLevel.DoesNotExist:
            return None

class ExamQuestion(models.Model):
    """Questions for entrance exams"""
    QUESTION_TYPES = [
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
    ]
    
    exam = models.ForeignKey(EntranceExam, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = ['exam', 'order']
    
    def __str__(self):
        return f"{self.exam.title} - Q{self.order}: {self.text[:50]}..."
    
    def get_correct_choices(self):
        """Get correct choices for this question"""
        return self.choices.filter(is_correct=True)

class ExamChoice(models.Model):
    """Choices for MCQ and T/F questions"""
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = ['question', 'order']
    
    def __str__(self):
        return f"{self.question.text[:30]}... - {self.text[:30]}..."

class ExamAttempt(models.Model):
    """Student attempts at entrance exams"""
    STATUS_CHOICES = [
        ('mcq_in_progress', 'MCQ Section In Progress'),
        ('mcq_completed', 'MCQ Section Completed'),
        ('speaking_pending', 'Speaking Section Pending'),
        ('speaking_completed', 'Speaking Section Completed'),
        ('writing_pending', 'Writing Section Pending'),
        ('writing_completed', 'Writing Section Completed'),
        ('fully_completed', 'Fully Completed'),
        ('graded', 'Graded'),
    ]
    
    exam = models.ForeignKey(EntranceExam, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='entrance_exam_attempts',
        limit_choices_to={'user_type': 'student'}
    )
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    mcq_completed_at = models.DateTimeField(null=True, blank=True)
    speaking_completed_at = models.DateTimeField(null=True, blank=True)
    writing_completed_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    # Status and scores
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='mcq_in_progress')
    mcq_score = models.PositiveIntegerField(default=0, help_text="Points earned in MCQ section")
    speaking_score = models.PositiveIntegerField(default=0, help_text="Points earned in speaking section")
    writing_score = models.PositiveIntegerField(default=0, help_text="Points earned in writing section")
    
    # Final results
    total_score = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Final percentage score"
    )
    achieved_level = models.ForeignKey(
        LanguageLevel, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Language level achieved"
    )
    
    # Grading notes
    speaking_notes = models.TextField(blank=True, help_text="Teacher's notes for speaking section")
    writing_notes = models.TextField(blank=True, help_text="Teacher's notes for writing section")
    general_feedback = models.TextField(blank=True, help_text="General feedback for student")
    
    class Meta:
        ordering = ['-started_at']
        unique_together = ['exam', 'student']  # One attempt per exam per student
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.exam.title} ({self.status})"
    
    def calculate_final_score(self):
        """Calculate final score and percentage"""
        self.total_score = self.mcq_score + self.speaking_score + self.writing_score
        total_possible = self.exam.get_total_points()
        
        if total_possible > 0:
            self.percentage = Decimal(str((self.total_score / total_possible) * 100)).quantize(Decimal('0.01'))
        else:
            self.percentage = Decimal('0.00')
        
        # Determine achieved level
        self.achieved_level = self.exam.get_level_for_score(float(self.percentage))
        self.save()
    
    def can_student_access_mcq(self):
        """Check if student can access MCQ section"""
        return self.status == 'mcq_in_progress'
    
    def can_teacher_grade_speaking(self):
        """Check if teacher can grade speaking section"""
        return self.status in ['mcq_completed', 'speaking_pending']
    
    def can_teacher_grade_writing(self):
        """Check if teacher can grade writing section"""
        return self.status in ['speaking_completed', 'writing_pending']
    
    def get_time_remaining_mcq(self):
        """Get remaining time for MCQ section"""
        if self.status != 'mcq_in_progress':
            return None
        
        from datetime import timedelta
        elapsed = timezone.now() - self.started_at
        total_allowed = timedelta(minutes=self.exam.mcq_time_limit_minutes)
        remaining = total_allowed - elapsed
        
        if remaining.total_seconds() <= 0:
            return timedelta(0)
        
        return remaining
    
    def auto_submit_mcq_if_expired(self):
        """Auto-submit MCQ section if time expired"""
        from datetime import timedelta
        if self.status == 'mcq_in_progress' and self.get_time_remaining_mcq() <= timedelta(0):
            self.mcq_completed_at = timezone.now()
            self.status = 'mcq_completed'
            self.save()
            return True
        return False

class ExamAnswer(models.Model):
    """Student answers for exam questions"""
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(ExamChoice, blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['attempt', 'question']
    
    def __str__(self):
        return f"{self.attempt.student.get_full_name()} - {self.question.text[:30]}..."
    
    def calculate_points(self):
        """Calculate points earned for this answer"""
        if self.question.question_type in ['multiple_choice', 'true_false']:
            correct_choices = set(self.question.get_correct_choices())
            selected_choices = set(self.selected_choices.all())
            
            if correct_choices == selected_choices and len(correct_choices) > 0:
                self.points_earned = self.question.points
                self.is_correct = True
            else:
                self.points_earned = 0
                self.is_correct = False
        
        self.save()
        return self.points_earned
