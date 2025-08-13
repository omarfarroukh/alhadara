from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    Language, LanguageLevel, EntranceExam, ExamQuestion,
    ExamChoice, ExamAttempt, ExamAnswer
)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_display_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']
    
    def get_display_name(self, obj):
        return obj.get_name_display()
    get_display_name.short_description = 'Display Name'

@admin.register(LanguageLevel)
class LanguageLevelAdmin(admin.ModelAdmin):
    list_display = ['level', 'get_display_name', 'min_score', 'max_score']
    list_filter = ['level']
    ordering = ['min_score']
    
    def get_display_name(self, obj):
        return obj.get_level_display()
    get_display_name.short_description = 'Display Name'

class ExamChoiceInline(admin.TabularInline):
    model = ExamChoice
    extra = 2
    fields = ['text', 'is_correct', 'order']
    ordering = ['order']

class ExamQuestionInline(admin.StackedInline):
    model = ExamQuestion
    extra = 0
    fields = ['text', 'question_type', 'points', 'order']
    ordering = ['order']
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if obj:
            # Limit questions to current exam
            formset.form.base_fields['exam'].queryset = EntranceExam.objects.filter(id=obj.id)
        return formset

@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ['get_exam_title', 'order', 'question_type', 'points', 'text_preview']
    list_filter = ['exam__language', 'question_type', 'exam']
    search_fields = ['text', 'exam__title']
    ordering = ['exam', 'order']
    inlines = [ExamChoiceInline]
    
    def get_exam_title(self, obj):
        return obj.exam.title
    get_exam_title.short_description = 'Exam'
    
    def text_preview(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_preview.short_description = 'Question Text'

@admin.register(EntranceExam)
class EntranceExamAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'language', 'grading_teacher', 'question_count',
        'total_points', 'is_active', 'created_at'
    ]
    list_filter = ['language', 'is_active', 'grading_teacher', 'created_at']
    search_fields = ['title', 'description', 'grading_teacher__first_name', 'grading_teacher__last_name']
    readonly_fields = ['qr_code', 'created_at', 'updated_at', 'total_points', 'question_count']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'language', 'grading_teacher', 'is_active')
        }),
        ('Exam Settings', {
            'fields': (
                'mcq_time_limit_minutes', 'mcq_total_points',
                'speaking_total_points', 'writing_total_points'
            )
        }),
        ('System Information', {
            'fields': ('qr_code', 'total_points', 'question_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ExamQuestionInline]
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    def total_points(self, obj):
        return obj.get_total_points()
    total_points.short_description = 'Total Points'

class ExamAnswerInline(admin.TabularInline):
    model = ExamAnswer
    extra = 0
    readonly_fields = ['question', 'selected_choices_display', 'points_earned', 'is_correct']
    fields = ['question', 'selected_choices_display', 'points_earned', 'is_correct']
    
    def selected_choices_display(self, obj):
        choices = obj.selected_choices.all()
        return ', '.join([choice.text for choice in choices]) if choices else 'No choices selected'
    selected_choices_display.short_description = 'Selected Choices'
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 'exam_title', 'language', 'status',
        'percentage', 'achieved_level', 'started_at', 'graded_at'
    ]
    list_filter = [
        'status', 'exam__language', 'achieved_level',
        'started_at', 'graded_at'
    ]
    search_fields = [
        'student__first_name', 'student__last_name',
        'exam__title', 'exam__language__name'
    ]
    readonly_fields = [
        'started_at', 'mcq_completed_at', 'speaking_completed_at',
        'writing_completed_at', 'graded_at', 'total_score',
        'percentage', 'achieved_level'
    ]
    ordering = ['-started_at']
    
    fieldsets = (
        ('Exam Information', {
            'fields': ('exam', 'student', 'status')
        }),
        ('Timestamps', {
            'fields': (
                'started_at', 'mcq_completed_at', 'speaking_completed_at',
                'writing_completed_at', 'graded_at'
            ),
            'classes': ('collapse',)
        }),
        ('Scores', {
            'fields': ('mcq_score', 'speaking_score', 'writing_score', 'total_score', 'percentage')
        }),
        ('Results', {
            'fields': ('achieved_level',)
        }),
        ('Grading Notes', {
            'fields': ('speaking_notes', 'writing_notes', 'general_feedback'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ExamAnswerInline]
    
    def student_name(self, obj):
        return obj.student.get_full_name()
    student_name.short_description = 'Student'
    
    def exam_title(self, obj):
        return obj.exam.title
    exam_title.short_description = 'Exam'
    
    def language(self, obj):
        return obj.exam.language.get_name_display()
    language.short_description = 'Language'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Recalculate final score if grading is complete
        if obj.status == 'graded':
            obj.calculate_final_score()

@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 'exam_title', 'question_preview',
        'points_earned', 'is_correct', 'answered_at'
    ]
    list_filter = [
        'is_correct', 'attempt__exam__language',
        'question__question_type', 'answered_at'
    ]
    search_fields = [
        'attempt__student__first_name', 'attempt__student__last_name',
        'attempt__exam__title', 'question__text'
    ]
    readonly_fields = ['answered_at', 'points_earned', 'is_correct']
    ordering = ['-answered_at']
    
    def student_name(self, obj):
        return obj.attempt.student.get_full_name()
    student_name.short_description = 'Student'
    
    def exam_title(self, obj):
        return obj.attempt.exam.title
    exam_title.short_description = 'Exam'
    
    def question_preview(self, obj):
        return obj.question.text[:50] + '...' if len(obj.question.text) > 50 else obj.question.text
    question_preview.short_description = 'Question'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Recalculate points when answer is saved
        obj.calculate_points()

# Custom admin actions
def mark_as_active(modeladmin, request, queryset):
    queryset.update(is_active=True)
mark_as_active.short_description = "Mark selected exams as active"

def mark_as_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
mark_as_inactive.short_description = "Mark selected exams as inactive"

# Add actions to EntranceExamAdmin
EntranceExamAdmin.actions = [mark_as_active, mark_as_inactive]
