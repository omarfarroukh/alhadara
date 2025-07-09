from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from courses.models import ScheduleSlot, Course
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Quiz(models.Model):
    """Quiz model that can be tied to a schedule slot"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    schedule_slot = models.ForeignKey(
        ScheduleSlot, 
        on_delete=models.CASCADE, 
        related_name='quizzes',
        null=True,
        blank=True,
        help_text="Optional: Link quiz to a specific schedule slot"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='quizzes',
        help_text="Course this quiz belongs to"
    )
    time_limit_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Time limit in minutes (0 for no limit)"
    )
    passing_score = models.PositiveIntegerField(
        default=70,
        help_text="Minimum score required to pass (percentage)"
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        help_text="Maximum number of attempts allowed"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Quizzes"
    
    def __str__(self):
        return f"{self.title} - {self.course.title}"
    
    def clean(self):
        """Validate quiz settings"""
        super().clean()
        
        if self.schedule_slot and self.schedule_slot.course != self.course:
            raise ValidationError("Schedule slot must belong to the same course")
        
        if self.passing_score > 100:
            raise ValidationError("Passing score cannot exceed 100%")
        
        if self.time_limit_minutes > 480:  # 8 hours max
            raise ValidationError("Time limit cannot exceed 8 hours")
    
    def get_available_until(self):
        """Get when the quiz becomes unavailable based on schedule slot"""
        if self.schedule_slot and self.schedule_slot.valid_until:
            return self.schedule_slot.valid_until
        return None
    
    def is_available_for_user(self, user):
        """Check if quiz is available for a specific user"""
        if not self.is_active:
            return False, "Quiz is not active"
        
        # Check if user is enrolled in the course
        if not user.enrollments.filter(
            course=self.course,
            status__in=['pending', 'active']
        ).exists():
            return False, "You must be enrolled in this course to take the quiz"
        
        # Check schedule slot availability
        if self.schedule_slot:
            today = timezone.now().date()
            if today < self.schedule_slot.valid_from:
                return False, f"Quiz will be available from {self.schedule_slot.valid_from}"
            if self.schedule_slot.valid_until and today > self.schedule_slot.valid_until:
                return False, "Quiz period has ended"
        
        # Check attempt limit
        user_attempts = QuizAttempt.objects.filter(
            quiz=self,
            user=user
        ).count()
        
        if user_attempts >= self.max_attempts:
            return False, f"You have reached the maximum attempts ({self.max_attempts})"
        
        return True, "Quiz is available"

class Question(models.Model):
    """Question model for quizzes"""
    QUESTION_TYPES = (
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    )
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    points = models.PositiveIntegerField(
        default=1,
        help_text="Points for this question (1-100)",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100)
        ]
    )    
    order = models.PositiveIntegerField(default=0, help_text="Question order in quiz")
    is_required = models.BooleanField(default=True)
    related_lessons = models.ManyToManyField('lessons.Lesson', blank=True, related_name='related_questions', help_text="Lessons related to this question for revision feedback.")
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}: {self.text[:50]}..."
    
    def get_correct_answers(self):
        """Get correct answers for this question"""
        if self.question_type == 'multiple_choice':
            return self.choices.filter(is_correct=True)
        elif self.question_type == 'true_false':
            return self.choices.filter(is_correct=True)
        return None

class Choice(models.Model):
    """Choice model for multiple choice and true/false questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"{self.question.text[:30]}... - {self.text[:30]}..."

class QuizAttempt(models.Model):
    """Model to track quiz attempts by users"""
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    )
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Score as percentage"
    )
    total_points = models.PositiveIntegerField(default=0)
    earned_points = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        unique_together = ['quiz', 'user', 'started_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.quiz.title} ({self.status})"
    
    def calculate_score(self):
        """Calculate and update the quiz score"""
        if self.status != 'completed':
            return
        
        total_possible = sum(q.points for q in self.quiz.questions.all())
        earned = sum(answer.points_earned for answer in self.answers.all())
        
        self.total_points = total_possible
        self.earned_points = earned
        
        if total_possible > 0:
            self.score = Decimal(str((earned / total_possible) * 100)).quantize(Decimal('0.01'))
        else:
            self.score = Decimal('0.00')
        
        self.passed = self.score >= self.quiz.passing_score
        self.save()
    
    def get_time_remaining(self):
        """Get remaining time for the quiz attempt"""
        if not self.quiz.time_limit_minutes:
            return None
        
        elapsed = timezone.now() - self.started_at
        remaining = timedelta(minutes=self.quiz.time_limit_minutes) - elapsed
        
        if remaining.total_seconds() <= 0:
            return timedelta(0)
        
        return remaining
    
    def is_time_expired(self):
        """Check if time has expired for this attempt"""
        if not self.quiz.time_limit_minutes:
            return False
        
        return self.get_time_remaining() <= timedelta(0)
    
    def auto_submit_if_expired(self):
        """Automatically submit quiz if time has expired"""
        if self.status == 'in_progress' and self.is_time_expired():
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.calculate_score()
            self.save()

class QuizAnswer(models.Model):
    """Model to store user answers to quiz questions"""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    text_answer = models.TextField(blank=True, help_text="For short answer and essay questions")
    points_earned = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['attempt', 'question']
    
    def __str__(self):
        return f"{self.attempt.user.get_full_name()} - {self.question.text[:30]}..."
    
    def calculate_points(self):
        """Calculate points earned for this answer"""
        if self.question.question_type in ['multiple_choice', 'true_false']:
            # Get correct choices
            correct_choices = set(self.question.get_correct_answers())
            # Get selected choices (refresh to ensure we have the latest)
            selected_choices = set(self.selected_choices.all())
            
            # Check if all correct choices are selected AND all selected choices are correct
            if correct_choices == selected_choices:
                self.points_earned = self.question.points
                self.is_correct = True
            else:
                self.points_earned = 0
                self.is_correct = False
        else:
            # For short answer and essay, manual grading required
            self.points_earned = 0
            self.is_correct = None
        
        self.save()
        return self.points_earned
