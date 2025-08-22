from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import *

User = get_user_model()

# ---------- Languages / Levels ----------
class LanguageSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    class Meta:
        model = Language
        fields = ['id', 'name', 'display_name', 'is_active', 'created_at']
    def get_display_name(self, obj): return dict(obj.LANGUAGE_CHOICES)[obj.name]

class LanguageLevelSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    class Meta:
        model = LanguageLevel
        fields = '__all__'
    def get_display_name(self, obj): return dict(obj.LEVEL_CHOICES)[obj.level]

# ---------- Question Bank ----------
class QuestionBankChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionBankChoice
        fields = ['id', 'text', 'is_correct', 'order']

class QuestionBankSerializer(serializers.ModelSerializer):
    choices = QuestionBankChoiceSerializer(many=True)
    class Meta:
        model = QuestionBank
        fields = ['id', 'language', 'text', 'question_type', 'difficulty', 'points', 'choices']

    def validate_choices(self, value):
        if sum(1 for c in value if c.get('is_correct')) != 1:
            raise serializers.ValidationError("Exactly one choice must be correct.")
        return value

    def create(self, validated):
        choices = validated.pop('choices')
        q = QuestionBank.objects.create(**validated)
        for c in choices:
            QuestionBankChoice.objects.create(question=q, **c)
        return q

class QuestionBankBulkSerializer(serializers.ListSerializer):
    child = QuestionBankSerializer()

    def create(self, validated_list):
        out = []
        for item in validated_list:
            choices = item.pop('choices')
            q = QuestionBank.objects.create(**item)
            for c in choices:
                QuestionBankChoice.objects.create(question=q, **c)
            out.append(q)
        return out

# ---------- Entrance Exam ----------
class EntranceExamSerializer(serializers.ModelSerializer):
    language_name = serializers.SerializerMethodField()
    grading_teacher_name = serializers.CharField(source='grading_teacher.get_full_name', read_only=True)
    total_points = serializers.SerializerMethodField()
    qr_image_base64 = serializers.ReadOnlyField()

    class Meta:
        model = EntranceExam
        fields = ['id', 'language', 'language_name', 'title', 'description',
                  'grading_teacher', 'grading_teacher_name', 'mcq_time_limit_minutes',
                  'mcq_total_points', 'speaking_total_points', 'writing_total_points',
                  'total_points', 'is_active', 'qr_code', 'created_at', 'updated_at',
                  'qr_image_base64']
        
    def get_total_points(self, obj): return obj.get_total_points()
    def get_language_name(self, obj): return dict(obj.language.LANGUAGE_CHOICES)[obj.language.name]

# ---------- Attempt runtime ----------
class AttemptChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttemptChoice
        fields = ['id', 'text', 'is_correct', 'order']

class AttemptQuestionSerializer(serializers.ModelSerializer):
    choices = AttemptChoiceSerializer(many=True, read_only=True)
    class Meta:
        model = AttemptQuestion
        fields = ['id', 'text', 'question_type', 'points', 'order', 'choices']

class MCQAnswerItemSerializer(serializers.Serializer):
    question = serializers.IntegerField(
        help_text="ID of the AttemptQuestion inside this attempt"
    )
    choice_index = serializers.IntegerField(
        min_value=1,
        max_value=4,
        help_text="1-4 for MCQ, 1-2 for True/False"
    )


class MCQBulkSubmitSerializer(serializers.Serializer):
    answers = serializers.ListField(
        child=MCQAnswerItemSerializer(),
        allow_empty=False
    )
    def validate(self, attrs):
        attempt = self.context['attempt']
        seen = set()
        for ans in attrs['answers']:
            q_id, idx = ans.get('question'), ans.get('choice_index')
            if q_id not in attempt.questions.values_list('id', flat=True):
                raise serializers.ValidationError(f"Question {q_id} invalid.")
            if q_id in seen:
                raise serializers.ValidationError(f"Question {q_id} duplicated.")
            seen.add(q_id)

            q = AttemptQuestion.objects.get(id=q_id)
            max_idx = 2 if q.question_type == 'true_false' else 4
            if not isinstance(idx, int) or idx < 1 or idx > max_idx:
                raise serializers.ValidationError(
                    f"choice_index for {q_id} must be 1..{max_idx}.")
        return attrs

class ExamAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    language_name = serializers.SerializerMethodField()
    achieved_level_display = serializers.SerializerMethodField()
    time_remaining_mcq = serializers.SerializerMethodField()
    can_access_mcq = serializers.SerializerMethodField()

    class Meta:
        model = ExamAttempt
        exclude = []
        read_only_fields = [
            'started_at', 'mcq_completed_at', 'speaking_completed_at',
            'writing_completed_at', 'graded_at', 'total_score', 'percentage',
            'achieved_level'
        ]

    def get_time_remaining_mcq(self, obj):
        r = obj.get_time_remaining_mcq()
        return int(r.total_seconds()) if r else None
    def get_can_access_mcq(self, obj): return obj.can_student_access_mcq()
    def get_language_name(self, obj):
        return dict(obj.exam.language.LANGUAGE_CHOICES)[obj.exam.language.name]
    def get_achieved_level_display(self, obj):
        return dict(obj.achieved_level.LEVEL_CHOICES)[obj.achieved_level.level] if obj.achieved_level else None

class ExamAttemptDetailSerializer(ExamAttemptSerializer):
    questions = AttemptQuestionSerializer(many=True, read_only=True)
    answers = serializers.SerializerMethodField()
    class Meta(ExamAttemptSerializer.Meta):
        pass
    def get_answers(self, obj):
        return [{"question": a.attempt_question.id,
                 "choice_index": a.selected_choice.order + 1 if a.selected_choice else None,
                 "is_correct": a.is_correct,
                 "points_earned": a.points_earned} for a in obj.answers.all()]
        
        
class TeacherGradeSerializer(serializers.Serializer):
    speaking_score = serializers.IntegerField(min_value=0)
    writing_score  = serializers.IntegerField(min_value=0)

    def validate(self, attrs):
        attempt = self.context['attempt']
        if attempt.status != 'mcq_completed':
            raise serializers.ValidationError("Can only grade after MCQ is graded.")
        return attrs
    
class QRSerializer(serializers.Serializer):
    qr_code = serializers.UUIDField(
        help_text="QR code UUID"
    )