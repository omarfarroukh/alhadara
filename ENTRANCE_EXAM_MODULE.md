# Language Entrance Exam Module

## Overview

The Language Entrance Exam Module is a comprehensive system for managing and conducting language proficiency tests. It supports multiple languages (English, German, French, Spanish) and provides automated MCQ/True-False grading with manual grading for speaking and writing sections.

## Features

### 1. Multi-Language Support
- **Supported Languages**: English, German, French, Spanish
- **Language Levels**: A1, A2, B1, B2, C1, C2 (CEFR framework)
- **Score Mapping**: Automatic level assignment based on percentage scores

### 2. Three-Part Exam Structure
- **MCQ/True-False Section**: Automated grading, timed section
- **Speaking Section**: Manual grading by assigned teacher
- **Writing Section**: Manual grading by assigned teacher

### 3. QR Code Access
- Each exam has a unique QR code for student access
- Prevents unauthorized access and ensures exam security

### 4. Teacher Assignment
- Each exam is assigned to a specific teacher for grading
- Teachers can only see and grade their assigned exams

### 5. Student Profile Integration
- Achieved language levels are automatically saved to student profiles
- Course enrollment validation based on language requirements

### 6. Course Language Requirements
- Courses can specify required language and minimum level
- Enrollment validation ensures students meet language prerequisites

## Models

### Language
Represents available languages for examination.

```python
- name: CharField (english, german, french, spanish)
- is_active: BooleanField
- created_at: DateTimeField
```

### LanguageLevel
Defines proficiency levels with score ranges.

```python
- level: CharField (a1, a2, b1, b2, c1, c2)
- min_score: PositiveIntegerField (0-100)
- max_score: PositiveIntegerField (0-100)
```

Score Mapping:
- A1: 0-29%
- A2: 30-49%
- B1: 50-69%
- B2: 70-84%
- C1: 85-94%
- C2: 95-100%

### EntranceExam
Main exam configuration.

```python
- language: ForeignKey to Language
- title: CharField
- description: TextField
- grading_teacher: ForeignKey to User (teacher)
- mcq_time_limit_minutes: PositiveIntegerField (default: 60)
- mcq_total_points: PositiveIntegerField (default: 100)
- speaking_total_points: PositiveIntegerField (default: 100)
- writing_total_points: PositiveIntegerField (default: 100)
- is_active: BooleanField
- qr_code: UUIDField (auto-generated)
```

### ExamQuestion
Questions for the MCQ/True-False section.

```python
- exam: ForeignKey to EntranceExam
- text: TextField
- question_type: CharField (multiple_choice, true_false)
- points: PositiveIntegerField (1-50)
- order: PositiveIntegerField
```

### ExamChoice
Answer choices for questions.

```python
- question: ForeignKey to ExamQuestion
- text: CharField
- is_correct: BooleanField
- order: PositiveIntegerField
```

### ExamAttempt
Student exam attempts with detailed tracking.

```python
- exam: ForeignKey to EntranceExam
- student: ForeignKey to User (student)
- started_at: DateTimeField
- mcq_completed_at: DateTimeField
- speaking_completed_at: DateTimeField
- writing_completed_at: DateTimeField
- graded_at: DateTimeField
- status: CharField (mcq_in_progress, mcq_completed, etc.)
- mcq_score: PositiveIntegerField
- speaking_score: PositiveIntegerField
- writing_score: PositiveIntegerField
- total_score: PositiveIntegerField
- percentage: DecimalField
- achieved_level: ForeignKey to LanguageLevel
- speaking_notes: TextField
- writing_notes: TextField
- general_feedback: TextField
```

Status Flow:
1. `mcq_in_progress` → `mcq_completed`
2. `mcq_completed` → `speaking_pending` → `speaking_completed`
3. `speaking_completed` → `writing_pending` → `writing_completed`
4. `writing_completed` → `fully_completed` → `graded`

### ExamAnswer
Student answers to MCQ/True-False questions.

```python
- attempt: ForeignKey to ExamAttempt
- question: ForeignKey to ExamQuestion
- selected_choices: ManyToManyField to ExamChoice
- points_earned: PositiveIntegerField
- is_correct: BooleanField
- answered_at: DateTimeField
```

## API Endpoints

### Base URL: `/api/entrance-exam/`

### Languages
- `GET /languages/` - List all active languages
- `GET /languages/{id}/` - Get language details

### Language Levels
- `GET /language-levels/` - List all language levels
- `GET /language-levels/{id}/` - Get level details

### Entrance Exams
- `GET /exams/` - List exams (filtered by user role)
- `POST /exams/` - Create new exam (teachers/admin only)
- `GET /exams/{id}/` - Get exam details with questions
- `PUT /exams/{id}/` - Update exam (teachers/admin only)
- `DELETE /exams/{id}/` - Delete exam (teachers/admin only)
- `POST /exams/start-by-qr/` - Start exam attempt using QR code
- `GET /exams/{id}/current-attempt/` - Get current user's attempt

### Exam Questions
- `GET /exams/{exam_id}/questions/` - List exam questions
- `POST /exams/{exam_id}/questions/` - Create question (teachers/admin only)
- `GET /exams/{exam_id}/questions/{id}/` - Get question details
- `PUT /exams/{exam_id}/questions/{id}/` - Update question (teachers/admin only)
- `DELETE /exams/{exam_id}/questions/{id}/` - Delete question (teachers/admin only)

### Exam Attempts
- `GET /attempts/` - List attempts (filtered by user role)
- `GET /attempts/{id}/` - Get attempt details
- `POST /attempts/{id}/answer-question/` - Submit answer to question
- `POST /attempts/{id}/submit-mcq/` - Submit MCQ section
- `PATCH /attempts/{id}/grade-attempt/` - Grade speaking/writing (teachers only)
- `GET /attempts/my-results/` - Get current user's exam results

### Exam Answers
- `GET /attempts/{attempt_id}/answers/` - List answers for attempt
- `GET /attempts/{attempt_id}/answers/{id}/` - Get answer details

## Usage Flow

### For Students

1. **Start Exam**
   ```http
   POST /api/entrance-exam/exams/start-by-qr/
   {
     "qr_code": "uuid-string"
   }
   ```

2. **Answer Questions**
   ```http
   POST /api/entrance-exam/attempts/{attempt_id}/answer-question/
   {
     "question": 1,
     "selected_choices": [1, 2]
   }
   ```

3. **Submit MCQ Section**
   ```http
   POST /api/entrance-exam/attempts/{attempt_id}/submit-mcq/
   ```

4. **View Results**
   ```http
   GET /api/entrance-exam/attempts/my-results/
   ```

### For Teachers

1. **Create Exam**
   ```http
   POST /api/entrance-exam/exams/
   {
     "language": 1,
     "title": "English Proficiency Test",
     "grading_teacher": 1,
     "mcq_time_limit_minutes": 60
   }
   ```

2. **Add Questions**
   ```http
   POST /api/entrance-exam/exams/{exam_id}/questions/
   {
     "text": "What is the capital of France?",
     "question_type": "multiple_choice",
     "points": 5,
     "order": 1,
     "choices": [
       {"text": "London", "is_correct": false, "order": 1},
       {"text": "Paris", "is_correct": true, "order": 2},
       {"text": "Berlin", "is_correct": false, "order": 3}
     ]
   }
   ```

3. **Grade Speaking/Writing**
   ```http
   PATCH /api/entrance-exam/attempts/{attempt_id}/grade-attempt/
   {
     "speaking_score": 85,
     "writing_score": 78,
     "speaking_notes": "Good pronunciation, needs more fluency",
     "writing_notes": "Grammar is strong, expand vocabulary",
     "general_feedback": "Well done overall!",
     "status": "graded"
   }
   ```

## Course Integration

### Language Requirements
Courses can now specify language requirements:

```python
# Course model additions
required_language: ForeignKey to Language (optional)
required_language_level: ForeignKey to LanguageLevel (optional)
```

### Enrollment Validation
The system automatically validates language requirements during enrollment:

```python
def can_student_enroll_language_wise(self, student):
    # Checks if student has achieved required language level
    # Returns (can_enroll: bool, message: str)
```

### Profile Integration
Student profiles automatically store achieved language levels:

```python
# Profile model additions
english_level: ForeignKey to LanguageLevel (optional)
german_level: ForeignKey to LanguageLevel (optional)
french_level: ForeignKey to LanguageLevel (optional)
spanish_level: ForeignKey to LanguageLevel (optional)
```

## Setup Instructions

### 1. Run Migrations
```bash
python manage.py makemigrations entranceexam
python manage.py makemigrations core
python manage.py makemigrations courses
python manage.py migrate
```

### 2. Initialize Language Data
```bash
python manage.py setup_language_data
```

### 3. Create Superuser and Test Data
```bash
python manage.py createsuperuser
```

### 4. Access Admin Interface
Visit `/admin/` to:
- Create languages and levels
- Set up entrance exams
- Manage questions and choices
- Monitor exam attempts
- Grade speaking/writing sections

## Security Features

1. **QR Code Access**: Prevents unauthorized exam access
2. **One Attempt Per Exam**: Students can only attempt each exam once
3. **Time Limits**: Automatic submission when time expires
4. **Role-Based Permissions**: Students, teachers, and admins have appropriate access
5. **Teacher Assignment**: Only assigned teachers can grade exams

## Validation Rules

1. **Language Levels**: Min score must be less than max score
2. **Exam Questions**: Must belong to the correct exam
3. **Answer Choices**: Must belong to the question being answered
4. **True/False Limit**: Only one choice can be selected for T/F questions
5. **Score Ranges**: Speaking/writing scores must be within defined limits
6. **Status Transitions**: Exam status must follow proper workflow

## Error Handling

The system provides comprehensive error messages for:
- Invalid QR codes
- Expired exam sessions
- Unauthorized access attempts
- Invalid score ranges
- Missing prerequisites
- Workflow violations

## Performance Optimizations

1. **Database Queries**: Optimized with select_related and prefetch_related
2. **Filtering**: Role-based queryset filtering
3. **Caching**: Ready for Redis caching implementation
4. **Indexing**: Proper database indexes on foreign keys

## Future Enhancements

1. **Audio Support**: File upload for speaking section
2. **Rich Text Editor**: For writing section questions
3. **Analytics Dashboard**: Exam performance statistics
4. **Bulk Operations**: Import/export questions
5. **Email Notifications**: Result notifications
6. **Multi-language UI**: Interface translation
7. **Advanced Reporting**: Detailed analytics and reports

## Conclusion

The Language Entrance Exam Module provides a complete solution for language proficiency testing with seamless integration into the course enrollment system. It ensures students meet language prerequisites while providing teachers with comprehensive grading tools and detailed feedback capabilities. 