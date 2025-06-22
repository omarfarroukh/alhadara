# Quiz System Documentation

## Overview

The Quiz System is a comprehensive Django application that integrates with your existing course management system. It allows you to create quizzes tied to schedule slots, with support for multiple question types, automatic scoring, time limits, and detailed analytics.

## Key Features

### 🎯 Core Functionality
- **Schedule Slot Integration**: Quizzes can be tied to specific schedule slots
- **Multiple Question Types**: Multiple choice, true/false, short answer, and essay questions
- **Automatic Scoring**: Objective questions are automatically graded
- **Manual Grading**: Essay and short answer questions can be manually graded
- **Time Limits**: Configurable time limits for quiz attempts
- **Attempt Tracking**: Multiple attempts with configurable limits
- **Availability Control**: Quizzes are only available to enrolled students

### 📊 Analytics & Reporting
- **Real-time Statistics**: Pass rates, average scores, score distributions
- **Detailed Results**: Individual question analysis and student performance
- **Progress Tracking**: Monitor student progress across multiple attempts

### 🔐 Security & Permissions
- **Role-based Access**: Different permissions for students, teachers, and admins
- **Enrollment Verification**: Only enrolled students can access quizzes
- **Attempt Validation**: Prevents unauthorized access and manipulation

## Models

### Quiz
The main quiz model that contains quiz settings and metadata.

```python
class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    schedule_slot = models.ForeignKey(ScheduleSlot, ...)  # Optional link to schedule slot
    course = models.ForeignKey(Course, ...)
    time_limit_minutes = models.PositiveIntegerField(default=30)
    passing_score = models.PositiveIntegerField(default=70)
    max_attempts = models.PositiveIntegerField(default=3)
    is_active = models.BooleanField(default=True)
```

### Question
Represents individual questions within a quiz.

```python
class Question(models.Model):
    QUESTION_TYPES = (
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    )
    
    quiz = models.ForeignKey(Quiz, ...)
    text = models.TextField()
    question_type = models.CharField(choices=QUESTION_TYPES)
    points = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
```

### Choice
Represents answer choices for multiple choice and true/false questions.

```python
class Choice(models.Model):
    question = models.ForeignKey(Question, ...)
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
```

### QuizAttempt
Tracks individual quiz attempts by students.

```python
class QuizAttempt(models.Model):
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    )
    
    quiz = models.ForeignKey(Quiz, ...)
    user = models.ForeignKey(User, ...)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(choices=STATUS_CHOICES, default='in_progress')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    total_points = models.PositiveIntegerField(default=0)
    earned_points = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(null=True, blank=True)
```

### QuizAnswer
Stores individual answers to questions within an attempt.

```python
class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, ...)
    question = models.ForeignKey(Question, ...)
    selected_choices = models.ManyToManyField(Choice, blank=True)
    text_answer = models.TextField(blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)
```

## API Endpoints

### Quiz Management

#### List Quizzes
```
GET /api/quiz/quizzes/
```
Returns all quizzes available to the user based on their role and enrollment.

**Query Parameters:**
- `course_id`: Filter by course
- `schedule_slot_id`: Filter by schedule slot
- `is_active`: Filter by active status
- `search`: Search in title and description

#### Create Quiz
```
POST /api/quiz/quizzes/
```
Create a new quiz (teachers/admins only).

**Required Fields:**
- `title`: Quiz title
- `course`: Course ID
- `time_limit_minutes`: Time limit in minutes
- `passing_score`: Minimum passing score (0-100)

**Optional Fields:**
- `description`: Quiz description
- `schedule_slot`: Schedule slot ID
- `max_attempts`: Maximum attempts allowed
- `is_active`: Whether quiz is active

#### Get Quiz Details
```
GET /api/quiz/quizzes/{id}/
```
Returns detailed quiz information including questions (for teachers/admins).

#### Start Quiz Attempt
```
POST /api/quiz/quizzes/{id}/start_attempt/
```
Start a new quiz attempt.

**Request Body:**
```json
{
    "quiz_id": 1
}
```

#### Submit Quiz Attempt
```
POST /api/quiz/quizzes/{id}/submit_attempt/
```
Submit a completed quiz attempt.

**Request Body:**
```json
{
    "attempt_id": 1
}
```

#### Get Quiz Statistics
```
GET /api/quiz/quizzes/{id}/statistics/
```
Get quiz statistics (teachers/admins only).

**Response:**
```json
{
    "total_attempts": 15,
    "unique_students": 12,
    "average_score": 78.5,
    "pass_rate": 73.3,
    "score_distribution": {
        "0-50": 2,
        "51-70": 4,
        "71-85": 6,
        "86-100": 3
    }
}
```

### Question Management

#### Create Question
```
POST /api/quiz/questions/
```
Create a new question with choices (teachers/admins only).

**Request Body:**
```json
{
    "quiz": 1,
    "text": "What is the correct way to create a function in Python?",
    "question_type": "multiple_choice",
    "points": 2,
    "order": 1,
    "choices": [
        {"text": "function myFunction():", "is_correct": false, "order": 1},
        {"text": "def myFunction():", "is_correct": true, "order": 2},
        {"text": "create myFunction():", "is_correct": false, "order": 3},
        {"text": "func myFunction():", "is_correct": false, "order": 4}
    ]
}
```

### Answer Management

#### Submit Answer
```
POST /api/quiz/answers/
```
Submit an answer to a question.

**Request Body:**
```json
{
    "attempt_id": 1,
    "question": 1,
    "choice_ids": [2],  // For multiple choice/true-false
    "text_answer": "Your answer here"  // For short answer/essay
}
```

#### Grade Answer (Manual)
```
POST /api/quiz/answers/{id}/grade/
```
Grade a manually graded answer (teachers/admins only).

**Request Body:**
```json
{
    "points_earned": 4,
    "is_correct": true
}
```

## Usage Examples

### Creating a Quiz with Questions

```python
from quiz.models import Quiz, Question, Choice

# Create quiz
quiz = Quiz.objects.create(
    title="Python Basics Quiz",
    description="Test your knowledge of Python programming",
    course=course,
    schedule_slot=schedule_slot,
    time_limit_minutes=30,
    passing_score=70,
    max_attempts=3
)

# Create multiple choice question
question = Question.objects.create(
    quiz=quiz,
    text="What is the correct way to create a function in Python?",
    question_type='multiple_choice',
    points=2,
    order=1
)

# Create choices
Choice.objects.create(question=question, text="function myFunction():", is_correct=False, order=1)
Choice.objects.create(question=question, text="def myFunction():", is_correct=True, order=2)
Choice.objects.create(question=question, text="create myFunction():", is_correct=False, order=3)
Choice.objects.create(question=question, text="func myFunction():", is_correct=False, order=4)
```

### Taking a Quiz

```python
# Check if quiz is available
is_available, message = quiz.is_available_for_user(student)
if is_available:
    # Start attempt
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        user=student,
        status='in_progress'
    )
    
    # Answer questions
    for question in quiz.questions.all():
        if question.question_type == 'multiple_choice':
            # Get correct choices
            correct_choices = question.get_correct_answers()
            
            # Create answer
            answer = QuizAnswer.objects.create(
                attempt=attempt,
                question=question
            )
            answer.selected_choices.set(correct_choices)
            answer.calculate_points()
    
    # Complete attempt
    attempt.status = 'completed'
    attempt.completed_at = timezone.now()
    attempt.calculate_score()
    attempt.save()
```

### Getting Quiz Statistics

```python
# Get quiz statistics
attempts = quiz.attempts.filter(status='completed')
stats = {
    'total_attempts': attempts.count(),
    'unique_students': attempts.values('user').distinct().count(),
    'average_score': attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0,
    'pass_rate': 0
}

if stats['total_attempts'] > 0:
    passed_attempts = attempts.filter(passed=True).count()
    stats['pass_rate'] = (passed_attempts / stats['total_attempts']) * 100
```

## Admin Interface

The quiz system includes a comprehensive Django admin interface:

### Quiz Admin
- List view with quiz details, question counts, and attempt counts
- Inline question editing
- Filtering by active status, course, and passing score
- Search functionality

### Question Admin
- List view with question previews
- Inline choice editing
- Filtering by question type and course
- Search functionality

### Quiz Attempt Admin
- List view with user, quiz, status, and score information
- Color-coded scores (green for pass, red for fail)
- Inline answer viewing
- Comprehensive filtering and search

### Quiz Answer Admin
- List view with student, question, and scoring information
- Manual grading interface
- Detailed answer tracking

## Integration with Schedule Slots

The quiz system integrates seamlessly with your existing schedule slot system:

### Availability Control
- Quizzes can be tied to specific schedule slots
- Availability is automatically checked based on schedule slot dates
- Students must be enrolled in the course to access quizzes

### Time Management
- Quiz time limits work independently of schedule slot times
- Quizzes can be taken outside of scheduled class times
- Schedule slot dates control when quizzes become available

### Course Integration
- Quizzes are always associated with a course
- Course enrollment is required for quiz access
- Quiz statistics are available at both quiz and course levels

## Security Features

### Access Control
- **Students**: Can only access quizzes for courses they're enrolled in
- **Teachers**: Can only manage quizzes for courses they teach
- **Admins/Reception**: Full access to all quizzes

### Data Protection
- Correct answers are not exposed to students in API responses
- Attempt validation prevents unauthorized access
- Score calculation is server-side only

### Validation
- Quiz availability is checked before allowing attempts
- Answer validation ensures data integrity
- Time limits are enforced server-side

## Testing

Run the test script to see the quiz system in action:

```bash
python test_quiz_system.py
```

This script demonstrates:
- Creating quizzes with different question types
- Student enrollment and quiz access
- Taking quizzes and automatic scoring
- Manual grading for essay questions
- Statistics and reporting

## Future Enhancements

Potential improvements for the quiz system:

1. **Advanced Question Types**: Drag-and-drop, matching, fill-in-the-blank
2. **Question Banks**: Reusable question pools
3. **Randomization**: Random question and choice ordering
4. **Proctoring**: Webcam monitoring and screen recording
5. **Certificates**: Automatic certificate generation for passing scores
6. **Notifications**: Email/SMS notifications for quiz availability
7. **Analytics Dashboard**: Advanced reporting and visualization
8. **Mobile Support**: Optimized mobile interface
9. **Offline Support**: Offline quiz taking with sync
10. **Integration**: LMS integration and SCORM support

## Support

For questions or issues with the quiz system:

1. Check the Django admin interface for data validation
2. Review the API documentation for endpoint usage
3. Run the test script to verify functionality
4. Check the Django logs for error messages
5. Verify user permissions and enrollment status

The quiz system is designed to be robust, secure, and easy to use while providing comprehensive functionality for educational assessment needs. 