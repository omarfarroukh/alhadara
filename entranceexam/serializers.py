from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Language, LanguageLevel, EntranceExam, ExamQuestion, 
    ExamChoice, ExamAttempt, ExamAnswer
)

User = get_user_model()

class LanguageSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Language
        fields = ['id', 'name', 'display_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_display_name(self, obj):
        return dict(obj.LANGUAGE_CHOICES)[obj.name]

class LanguageLevelSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = LanguageLevel
        fields = ['id', 'level', 'display_name', 'min_score', 'max_score']
        read_only_fields = ['id']
    
    def get_display_name(self, obj):
        return dict(obj.LEVEL_CHOICES)[obj.level]

class ExamChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamChoice
        fields = ['id', 'text', 'is_correct', 'order']
        read_only_fields = ['id']

class ExamChoiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamChoice
        fields = ['text', 'is_correct', 'order']

class ExamQuestionSerializer(serializers.ModelSerializer):
    choices = ExamChoiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = ExamQuestion
        fields = ['id', 'text', 'question_type', 'points', 'order', 'choices']
        read_only_fields = ['id']

class ExamQuestionCreateSerializer(serializers.ModelSerializer):
    choices = ExamChoiceCreateSerializer(many=True, write_only=True)
    
    class Meta:
        model = ExamQuestion
        fields = ['text', 'question_type', 'points', 'order', 'choices']
    
    def create(self, validated_data):
        choices_data = validated_data.pop('choices', [])
        question = ExamQuestion.objects.create(**validated_data)
        
        for choice_data in choices_data:
            ExamChoice.objects.create(question=question, **choice_data)
        
        return question

class EntranceExamSerializer(serializers.ModelSerializer):
    language_name = serializers.SerializerMethodField()
    grading_teacher_name = serializers.CharField(source='grading_teacher.get_full_name', read_only=True)
    total_points = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    qr_image_base64 = serializers.ReadOnlyField()

    
    class Meta:
        model = EntranceExam
        fields = [
            'id', 'language', 'language_name', 'title', 'description',
            'grading_teacher', 'grading_teacher_name', 'mcq_time_limit_minutes',
            'mcq_total_points', 'speaking_total_points', 'writing_total_points',
            'total_points', 'question_count', 'is_active', 'qr_code',
            'created_at', 'updated_at','qr_image_base64'
        ]
        read_only_fields = ['id', 'qr_code', 'created_at', 'updated_at']
    
    def get_total_points(self, obj):
        return obj.get_total_points()
    
    def get_question_count(self, obj):
        return obj.questions.count()
    
    def get_language_name(self, obj):
        return dict(obj.language.LANGUAGE_CHOICES)[obj.language.name]

class EntranceExamDetailSerializer(EntranceExamSerializer):
    questions = ExamQuestionSerializer(many=True, read_only=True)
    
    class Meta(EntranceExamSerializer.Meta):
        fields = EntranceExamSerializer.Meta.fields + ['questions']

class EntranceExamCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntranceExam
        fields = [
            'language', 'title', 'description', 'grading_teacher',
            'mcq_time_limit_minutes', 'mcq_total_points', 
            'speaking_total_points', 'writing_total_points', 'is_active'
        ]

class ExamAnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    selected_choices_text = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamAnswer
        fields = [
            'id', 'question', 'question_text', 'selected_choices',
            'selected_choices_text', 'points_earned', 'is_correct', 'answered_at'
        ]
        read_only_fields = ['id', 'points_earned', 'is_correct', 'answered_at']
    
    def get_selected_choices_text(self, obj):
        return [choice.text for choice in obj.selected_choices.all()]

class ExamAnswerSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAnswer
        fields = ['question', 'selected_choices']
    
    def validate(self, data):
        question = data.get('question')
        selected_choices = data.get('selected_choices', [])
        
        # Validate that all selected choices belong to the question
        for choice in selected_choices:
            if choice.question != question:
                raise serializers.ValidationError(
                    f"Choice '{choice.text}' does not belong to the specified question"
                )
        
        # Validate question type constraints
        if question.question_type == 'true_false' and len(selected_choices) > 1:
            raise serializers.ValidationError(
                "True/False questions can only have one selected choice"
            )
        
        return data

class ExamAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    language_name = serializers.SerializerMethodField()
    achieved_level_display = serializers.SerializerMethodField()
    time_remaining_mcq = serializers.SerializerMethodField()
    can_access_mcq = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam', 'exam_title', 'language_name', 'student', 'student_name',
            'started_at', 'mcq_completed_at', 'speaking_completed_at',
            'writing_completed_at', 'graded_at', 'status', 'mcq_score',
            'speaking_score', 'writing_score', 'total_score', 'percentage',
            'achieved_level', 'achieved_level_display', 'speaking_notes',
            'writing_notes', 'general_feedback', 'time_remaining_mcq',
            'can_access_mcq'
        ]
        read_only_fields = [
            'id', 'started_at', 'mcq_completed_at', 'speaking_completed_at',
            'writing_completed_at', 'graded_at', 'total_score', 'percentage',
            'achieved_level'
        ]
    
    def get_time_remaining_mcq(self, obj):
        remaining = obj.get_time_remaining_mcq()
        if remaining:
            return int(remaining.total_seconds())
        return None
    
    def get_can_access_mcq(self, obj):
        return obj.can_student_access_mcq()
    
    def get_language_name(self, obj):
        if obj.exam and obj.exam.language:
            return dict(obj.exam.language.LANGUAGE_CHOICES)[obj.exam.language.name]
        return None
    
    def get_achieved_level_display(self, obj):
        if obj.achieved_level:
            return dict(obj.achieved_level.LEVEL_CHOICES)[obj.achieved_level.level]
        return None

class ExamAttemptDetailSerializer(ExamAttemptSerializer):
    answers = ExamAnswerSerializer(many=True, read_only=True)
    
    class Meta(ExamAttemptSerializer.Meta):
        fields = ExamAttemptSerializer.Meta.fields + ['answers']

class ExamStartSerializer(serializers.Serializer):
    qr_code = serializers.UUIDField()
    
    def validate_qr_code(self, value):
        try:
            exam = EntranceExam.objects.get(qr_code=value, is_active=True)
        except EntranceExam.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive exam QR code")
        return value

class ExamSubmitSerializer(serializers.Serializer):
    """Serializer for submitting MCQ section"""
    pass

class ExamGradingSerializer(serializers.ModelSerializer):
    """Serializer for teacher grading of speaking/writing sections"""
    class Meta:
        model = ExamAttempt
        fields = [
            'speaking_score', 'writing_score', 'speaking_notes',
            'writing_notes', 'general_feedback', 'status'
        ]
    
    def validate(self, data):
        instance = self.instance
        new_status = data.get('status', instance.status)
        
        # Validate status transitions
        valid_transitions = {
            'mcq_completed': ['speaking_pending', 'speaking_completed'],
            'speaking_pending': ['speaking_completed'],
            'speaking_completed': ['writing_pending', 'writing_completed'],
            'writing_pending': ['writing_completed'],
            'writing_completed': ['fully_completed'],
            'fully_completed': ['graded']
        }
        
        if instance.status in valid_transitions:
            if new_status not in valid_transitions[instance.status]:
                raise serializers.ValidationError(
                    f"Cannot change status from {instance.status} to {new_status}"
                )
        
        # Validate score ranges
        speaking_score = data.get('speaking_score', instance.speaking_score)
        writing_score = data.get('writing_score', instance.writing_score)
        
        if speaking_score < 0 or speaking_score > instance.exam.speaking_total_points:
            raise serializers.ValidationError(
                f"Speaking score must be between 0 and {instance.exam.speaking_total_points}"
            )
        
        if writing_score < 0 or writing_score > instance.exam.writing_total_points:
            raise serializers.ValidationError(
                f"Writing score must be between 0 and {instance.exam.writing_total_points}"
            )
        
        return data

class StudentResultSerializer(serializers.ModelSerializer):
    """Serializer for student to view their exam results"""
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    language_name = serializers.SerializerMethodField()
    achieved_level_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamAttempt
        fields = [
            'id', 'exam_title', 'language_name', 'started_at', 'graded_at',
            'status', 'mcq_score', 'speaking_score', 'writing_score',
            'total_score', 'percentage', 'achieved_level_display',
            'general_feedback'
        ]
        read_only_fields = fields
    
    def get_language_name(self, obj):
        if obj.exam and obj.exam.language:
            return dict(obj.exam.language.LANGUAGE_CHOICES)[obj.exam.language.name]
        return None
    
    def get_achieved_level_display(self, obj):
        if obj.achieved_level:
            return dict(obj.achieved_level.LEVEL_CHOICES)[obj.achieved_level.level]
        return None 