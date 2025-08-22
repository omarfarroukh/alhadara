# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import (
    Language,
    LanguageLevel,
    EntranceExam,
    ExamTemplate,
    QuestionBank,
    QuestionBankChoice,
    AttemptQuestion,
    AttemptChoice,
    AttemptAnswer,
)


# ------------------------------------------------------------------
# 1.  Languages  (unchanged)
# ------------------------------------------------------------------
@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_display_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']

    def get_display_name(self, obj):
        return obj.get_name_display()
    get_display_name.short_description = 'Display Name'


# ------------------------------------------------------------------
# 2.  Language Levels  (unchanged)
# ------------------------------------------------------------------
@admin.register(LanguageLevel)
class LanguageLevelAdmin(admin.ModelAdmin):
    list_display = ['level', 'get_display_name', 'min_score', 'max_score']
    list_filter = ['level']
    ordering = ['min_score']

    def get_display_name(self, obj):
        return obj.get_level_display()
    get_display_name.short_description = 'Display Name'


# ------------------------------------------------------------------
# 3.  Question Bank
# ------------------------------------------------------------------
class QuestionBankChoiceInline(admin.TabularInline):
    model = QuestionBankChoice
    extra = 3
    fields = ['text', 'is_correct', 'order']
    ordering = ['order']


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ['language', 'difficulty', 'text_preview', 'points', 'question_type']
    list_filter = ['language', 'difficulty', 'question_type']
    search_fields = ['text']
    inlines = [QuestionBankChoiceInline]

    def text_preview(self, obj):
        return obj.text[:100] + '...' if len(obj.text) > 100 else obj.text
    text_preview.short_description = 'Question Text'


# ------------------------------------------------------------------
# 4.  Exam Template
# ------------------------------------------------------------------
@admin.register(ExamTemplate)
class ExamTemplateAdmin(admin.ModelAdmin):
    list_display = ('exam', 'counts')
    search_fields = ['exam__title']


# ------------------------------------------------------------------
# 5.  Entrance Exam  (no inline questions any more)
# ------------------------------------------------------------------
@admin.register(EntranceExam)
class EntranceExamAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'language', 'grading_teacher',
        'total_points', 'is_active', 'created_at'
    ]
    list_filter = ['language', 'is_active', 'grading_teacher', 'created_at']
    search_fields = [
        'title', 'description',
        'grading_teacher__first_name', 'grading_teacher__last_name'
    ]
    readonly_fields = ['qr_code', 'created_at', 'updated_at', 'total_points']
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
            'fields': ('qr_code', 'total_points', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def total_points(self, obj):
        return obj.get_total_points()
    total_points.short_description = 'Total Points'


# ------------------------------------------------------------------
# 6.  Attempt Answer (inspection only)
# ------------------------------------------------------------------
@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = [
        'student_name', 'exam_title', 'question_preview',
        'choice_text', 'is_correct', 'points_earned', 'answered_at'
    ]
    list_filter = ['is_correct', 'answered_at', 'attempt__exam__language']
    search_fields = [
        'attempt__student__first_name', 'attempt__student__last_name',
        'attempt__exam__title', 'attempt_question__text'
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
        return obj.attempt_question.text[:50] + '...' if len(obj.attempt_question.text) > 50 else obj.attempt_question.text
    question_preview.short_description = 'Question'

    def choice_text(self, obj):
        return obj.selected_choice.text if obj.selected_choice else '-'
    choice_text.short_description = 'Selected Choice'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.calculate_points()