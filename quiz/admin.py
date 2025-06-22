from django.contrib import admin
from django.utils.html import format_html
from .models import Quiz, Question, Choice, QuizAttempt, QuizAnswer

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    fields = ['text', 'is_correct', 'order']

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['text', 'question_type', 'points', 'order', 'is_required']
    inlines = [ChoiceInline]

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'course', 'schedule_slot', 'time_limit_minutes', 
        'passing_score', 'is_active', 'questions_count', 'attempts_count'
    ]
    list_filter = ['is_active', 'course', 'passing_score', 'created_at']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'course', 'schedule_slot')
        }),
        ('Quiz Settings', {
            'fields': ('time_limit_minutes', 'passing_score', 'max_attempts', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = 'Questions'
    
    def attempts_count(self, obj):
        return obj.attempts.count()
    attempts_count.short_description = 'Attempts'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        'text_preview', 'quiz', 'question_type', 'points', 'order', 'is_required'
    ]
    list_filter = ['question_type', 'is_required', 'quiz__course']
    search_fields = ['text', 'quiz__title']
    inlines = [ChoiceInline]
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Question Text'

@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ['text_preview', 'question', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__question_type']
    search_fields = ['text', 'question__text']
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Choice Text'

class QuizAnswerInline(admin.TabularInline):
    model = QuizAnswer
    extra = 0
    readonly_fields = ['question', 'points_earned', 'is_correct', 'answered_at']
    fields = ['question', 'points_earned', 'is_correct', 'answered_at']

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'quiz', 'status', 'score_display', 'passed', 'started_at', 'completed_at'
    ]
    list_filter = ['status', 'passed', 'quiz__course', 'started_at']
    search_fields = ['user__first_name', 'user__last_name', 'quiz__title']
    readonly_fields = ['started_at', 'completed_at', 'score', 'total_points', 'earned_points']
    inlines = [QuizAnswerInline]
    
    fieldsets = (
        ('Attempt Information', {
            'fields': ('user', 'quiz', 'status', 'passed')
        }),
        ('Scoring', {
            'fields': ('score', 'total_points', 'earned_points')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at')
        }),
    )
    
    def score_display(self, obj):
        if obj.score is not None:
            color = 'green' if obj.passed else 'red'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, obj.score
            )
        return 'N/A'
    score_display.short_description = 'Score'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'quiz')

@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'attempt_user', 'question_preview', 'question_type', 
        'points_earned', 'is_correct', 'answered_at'
    ]
    list_filter = ['is_correct', 'question__question_type', 'answered_at']
    search_fields = ['attempt__user__first_name', 'attempt__user__last_name', 'question__text']
    readonly_fields = ['attempt', 'question', 'points_earned', 'is_correct', 'answered_at']
    
    def attempt_user(self, obj):
        return obj.attempt.user.get_full_name()
    attempt_user.short_description = 'Student'
    
    def question_preview(self, obj):
        return obj.question.text[:50] + '...' if len(obj.question.text) > 50 else obj.question.text
    question_preview.short_description = 'Question'
    
    def question_type(self, obj):
        return obj.question.get_question_type_display()
    question_type.short_description = 'Type'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'attempt__user', 'question'
        ).prefetch_related('selected_choices')
