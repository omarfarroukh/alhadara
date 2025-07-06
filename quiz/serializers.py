from rest_framework import serializers
from .models import Quiz, Question, Choice, QuizAttempt, QuizAnswer
from courses.serializers import CourseSerializer, ScheduleSlotSerializer
from lessons.models import Lesson

class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'order']
        read_only_fields = ['is_correct']  # Don't expose correct answers to students

class ChoiceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating choices with correct answer information"""
    is_correct = serializers.BooleanField(
        help_text="Mark this choice as the correct answer. For multiple choice questions, you can have multiple correct answers. For true/false questions, exactly one choice must be marked as correct."
    )
    
    class Meta:
        model = Choice
        fields = ['text', 'is_correct', 'order']
    
    def validate(self, data):
        """Validate choice data"""
        # Ensure at least one choice is marked as correct for multiple choice/true_false questions
        # This validation will be handled at the question level
        return data

class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)
    related_lessons = serializers.SerializerMethodField()
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'points', 'order', 'is_required', 'choices', 'related_lessons']

    def get_related_lessons(self, obj):
        return [{'id': l.id, 'title': l.title} for l in obj.related_lessons.all()]

class QuizSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    schedule_slot = ScheduleSlotSerializer(read_only=True)
    questions_count = serializers.SerializerMethodField()
    user_attempts_count = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    availability_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'course', 'schedule_slot',
            'time_limit_minutes', 'passing_score', 'max_attempts',
            'is_active', 'created_at', 'updated_at',
            'questions_count', 'user_attempts_count', 'is_available', 'availability_message'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_questions_count(self, obj):
        return obj.questions.count()
    
    def get_user_attempts_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.attempts.filter(user=request.user).count()
        return 0
    
    def get_is_available(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            is_available, _ = obj.is_available_for_user(request.user)
            return is_available
        return False
    
    def get_availability_message(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            _, message = obj.is_available_for_user(request.user)
            return message
        return "Login required"

class QuizDetailSerializer(QuizSerializer):
    """Detailed quiz serializer with questions for teachers/admins"""
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta(QuizSerializer.Meta):
        fields = QuizSerializer.Meta.fields + ['questions']

class QuizCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating quizzes"""
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'course', 'schedule_slot',
            'time_limit_minutes', 'passing_score', 'max_attempts', 'is_active'
        ]
        read_only_fields = ['id']  # ID is read-only as it's auto-generated
    
    def validate(self, data):
        """Validate quiz data"""
        if data.get('schedule_slot') and data.get('course'):
            if data['schedule_slot'].course != data['course']:
                raise serializers.ValidationError(
                    "Schedule slot must belong to the same course"
                )
        return data

class QuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating questions"""
    choices = ChoiceCreateSerializer(many=True, required=False)
    related_lessons = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all(), many=True, required=False)
    
    class Meta:
        model = Question
        fields = ['quiz', 'text', 'question_type', 'points', 'order', 'is_required', 'choices', 'related_lessons']
    
    def validate(self, data):
        """Validate question data"""
        quiz = data.get('quiz')
        if quiz and not quiz.is_active:
            raise serializers.ValidationError("Cannot add questions to inactive quizzes")
        
        # Validate choices for multiple choice and true/false questions
        choices_data = data.get('choices', [])
        question_type = data.get('question_type')
        
        if question_type in ['multiple_choice', 'true_false']:
            if not choices_data:
                raise serializers.ValidationError(
                    f"{question_type.replace('_', ' ').title()} questions must have at least one choice"
                )
            
            # Check if exactly one choice is marked as correct
            correct_choices = [choice for choice in choices_data if choice.get('is_correct', False)]
            if len(correct_choices) != 1:
                raise serializers.ValidationError(
                    f"Exactly one choice must be marked as correct for {question_type.replace('_', ' ')} questions"
                )
        
        elif question_type in ['short_answer', 'essay']:
            if choices_data:
                raise serializers.ValidationError(
                    f"{question_type.replace('_', ' ').title()} questions should not have choices"
                )
        
        return data
    
    def create(self, validated_data):
        choices_data = validated_data.pop('choices', [])
        related_lessons = validated_data.pop('related_lessons', [])
        question = Question.objects.create(**validated_data)
        if related_lessons:
            question.related_lessons.set(related_lessons)
        for choice_data in choices_data:
            Choice.objects.create(question=question, **choice_data)
        return question
    
    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', [])
        related_lessons = validated_data.pop('related_lessons', None)
        instance = super().update(instance, validated_data)
        if related_lessons is not None:
            instance.related_lessons.set(related_lessons)
        # Update choices
        instance.choices.all().delete()
        for choice_data in choices_data:
            Choice.objects.create(question=instance, **choice_data)
        return instance

class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer for quiz attempts"""
    quiz_title = serializers.ReadOnlyField(source='quiz.title')
    user_name = serializers.ReadOnlyField(source='user.get_full_name')
    time_remaining = serializers.SerializerMethodField()
    is_time_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'user', 'user_name',
            'started_at', 'completed_at', 'status', 'score',
            'total_points', 'earned_points', 'passed',
            'time_remaining', 'is_time_expired'
        ]
        read_only_fields = [
            'user', 'started_at', 'completed_at', 'status',
            'score', 'total_points', 'earned_points', 'passed'
        ]
    
    def get_time_remaining(self, obj):
        remaining = obj.get_time_remaining()
        if remaining:
            return int(remaining.total_seconds())
        return None
    
    def get_is_time_expired(self, obj):
        return obj.is_time_expired()

class QuizAnswerSerializer(serializers.ModelSerializer):
    """Serializer for quiz answers"""
    question_text = serializers.ReadOnlyField(source='question.text')
    question_type = serializers.ReadOnlyField(source='question.question_type')
    selected_choices = ChoiceSerializer(many=True, read_only=True)
    revision_note = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAnswer
        fields = [
            'id', 'attempt', 'question', 'question_text', 'question_type',
            'selected_choices', 'text_answer', 'points_earned', 'is_correct', 'answered_at', 'revision_note'
        ]
        read_only_fields = ['attempt', 'points_earned', 'is_correct', 'answered_at']

    def get_revision_note(self, obj):
        if obj.is_correct is False:
            lessons = obj.question.related_lessons.all()
            if lessons:
                return {
                    'message': 'Please revise the following lessons:',
                    'lessons': [{'id': l.id, 'title': l.title} for l in lessons]
                }
        return None

class QuizAnswerSubmitSerializer(serializers.ModelSerializer):
    """Serializer for submitting quiz answers"""
    attempt_id = serializers.IntegerField(
        help_text="ID of the quiz attempt this answer belongs to",
        write_only=True
    )
    question_order = serializers.IntegerField(
        help_text="Order number of the question in the quiz (1, 2, 3, etc.)",
        write_only=True
    )
    choice_orders = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text="List of choice order numbers for multiple choice/true-false questions (1, 2, 3, etc.)"
    )
    
    class Meta:
        model = QuizAnswer
        fields = ['id', 'attempt', 'question', 'text_answer', 'points_earned', 'is_correct', 'answered_at', 'attempt_id', 'question_order', 'choice_orders']
        read_only_fields = ['id', 'attempt', 'question', 'points_earned', 'is_correct', 'answered_at']
    
    def validate(self, data):
        attempt = self.context.get('_attempt')
        question = self.context.get('_question')
        request = self.context['request']

        attempt_id = data.get('attempt_id')
        question_order = data.get('question_order')
        choice_orders = data.get('choice_orders', [])
        text_answer = data.get('text_answer', '')

        # Use pre-fetched attempt if available
        if not attempt:
            try:
                attempt = QuizAttempt.objects.get(
                    id=attempt_id,
                    user=request.user,
                    status='in_progress'
                )
            except QuizAttempt.DoesNotExist:
                raise serializers.ValidationError("Invalid attempt or attempt not in progress")

        # Use pre-fetched question if available
        if not question:
            try:
                question = attempt.quiz.questions.get(order=question_order)
            except Question.DoesNotExist:
                raise serializers.ValidationError(
                    f"Question with order {question_order} not found in this quiz"
                )

        # Validate based on question type
        if question.question_type in ['multiple_choice', 'true_false']:
            if not choice_orders:
                raise serializers.ValidationError(
                    "You must select at least one choice for this question type"
                )
            valid_orders = set(question.choices.values_list('order', flat=True))
            if not set(choice_orders).issubset(valid_orders):
                raise serializers.ValidationError(
                    f"Invalid choice orders. Valid orders: {sorted(valid_orders)}"
                )

        elif question.question_type in ['short_answer', 'essay']:
            if not text_answer.strip():
                raise serializers.ValidationError("Text answer is required for this question type")

        data['_attempt'] = attempt
        data['_question'] = question
        return data

    def create(self, validated_data):
        question = validated_data.pop('_question')
        attempt = validated_data.pop('_attempt')
        choice_orders = validated_data.pop('choice_orders', [])
        
        # Create the answer
        answer = QuizAnswer.objects.create(
            attempt=attempt,
            question=question,
            text_answer=validated_data.get('text_answer', '')
        )
        
        # Set selected choices by order
        if choice_orders:
            choices = question.choices.filter(order__in=choice_orders)
            answer.selected_choices.set(choices)
            # Refresh the answer to ensure the relationship is established
            answer.refresh_from_db()
        
        # Calculate points for auto-graded questions
        answer.calculate_points()
        
        return answer

class QuizStartSerializer(serializers.Serializer):
    """Serializer for starting a quiz attempt"""
    quiz_id = serializers.IntegerField()
    
    def validate_quiz_id(self, value):
        """Validate quiz exists and is available"""
        try:
            quiz = Quiz.objects.get(id=value)
        except Quiz.DoesNotExist:
            raise serializers.ValidationError("Quiz not found")
        
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            is_available, message = quiz.is_available_for_user(request.user)
            if not is_available:
                raise serializers.ValidationError(message)
        
        return value

class QuizSubmitSerializer(serializers.Serializer):
    """Serializer for submitting a completed quiz"""
    attempt_id = serializers.IntegerField()
    
    def validate_attempt_id(self, value):
        """Validate attempt exists and belongs to user"""
        try:
            attempt = QuizAttempt.objects.get(id=value)
        except QuizAttempt.DoesNotExist:
            raise serializers.ValidationError("Quiz attempt not found")
        
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if attempt.user != request.user:
                raise serializers.ValidationError("This attempt does not belong to you")
            
            if attempt.status != 'in_progress':
                raise serializers.ValidationError("This attempt has already been submitted")
        
        return value

class QuizResultSerializer(serializers.ModelSerializer):
    """Serializer for quiz results"""
    quiz_title = serializers.ReadOnlyField(source='quiz.title')
    user_name = serializers.ReadOnlyField(source='user.get_full_name')
    answers = QuizAnswerSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'user', 'user_name',
            'started_at', 'completed_at', 'status', 'score',
            'total_points', 'earned_points', 'passed', 'answers'
        ] 
        
class QuizAnswerItemSerializer(serializers.Serializer):
    question_order = serializers.IntegerField()
    choice_orders = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=[]
    )
    text_answer = serializers.CharField(
        required=False,
        allow_blank=True,
        default=""
    )

class QuizBulkSubmitSerializer(QuizSubmitSerializer):
    answers = QuizAnswerItemSerializer(many=True)

    def validate(self, data):
        """Validate all answers belong to the same quiz"""
        attempt_id = data['attempt_id']
        answers = data['answers']
        
        try:
            attempt = QuizAttempt.objects.select_related('quiz').get(id=attempt_id)
            questions = attempt.quiz.questions.all()
            question_orders = {q.order: q for q in questions}
            
            # Validate all question orders exist in this quiz
            for answer in answers:
                if answer['question_order'] not in question_orders:
                    raise serializers.ValidationError({
                        'question_order': f"Question order {answer['question_order']} not found in this quiz"
                    })
        
        except QuizAttempt.DoesNotExist:
            raise serializers.ValidationError("Quiz attempt not found")
        
        return data