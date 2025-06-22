#!/usr/bin/env python
"""
Test script for the Quiz System
This script demonstrates how to create and use quizzes tied to schedule slots
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Department, CourseType, Course, Hall, ScheduleSlot
from quiz.models import Quiz, Question, Choice, QuizAttempt, QuizAnswer
from core.models import Profile, Interest, StudyField, University, ProfileInterest

User = get_user_model()

def create_test_data():
    """Create test data for the quiz system"""
    print("Creating test data for quiz system...")
    
    # Create department and course type
    dept, created = Department.objects.get_or_create(
        name="Computer Science",
        defaults={'description': 'Computer Science Department'}
    )
    print(f"Department: {dept}")
    
    course_type, created = CourseType.objects.get_or_create(
        name="Programming",
        defaults={'department': dept}
    )
    print(f"Course Type: {course_type}")
    
    # Create course
    course, created = Course.objects.get_or_create(
        title="Python Programming Basics",
        defaults={
            'description': 'Learn the fundamentals of Python programming',
            'price': Decimal('150.00'),
            'duration': 20,
            'max_students': 15,
            'certification_eligible': True,
            'category': 'course',
            'department': dept,
            'course_type': course_type
        }
    )
    print(f"Course: {course}")
    
    # Create hall
    hall, created = Hall.objects.get_or_create(
        name="Lab 101",
        defaults={
            'capacity': 20,
            'location': 'Building A, First Floor',
            'hourly_rate': Decimal('25.00')
        }
    )
    print(f"Hall: {hall}")
    
    # Create schedule slot
    today = datetime.now().date()
    schedule_slot, created = ScheduleSlot.objects.get_or_create(
        course=course,
        hall=hall,
        defaults={
            'days_of_week': ['mon', 'wed', 'fri'],
            'start_time': datetime.strptime('14:00', '%H:%M').time(),
            'end_time': datetime.strptime('16:00', '%H:%M').time(),
            'recurring': True,
            'valid_from': today,
            'valid_until': today + timedelta(days=30)
        }
    )
    print(f"Schedule Slot: {schedule_slot}")
    
    # Create teacher
    teacher, created = User.objects.get_or_create(
        phone='teacher123',
        defaults={
            'first_name': 'John',
            'middle_name': 'A',
            'last_name': 'Smith',
            'user_type': 'teacher',
            'is_active': True
        }
    )
    print(f"Teacher: {teacher}")
    
    # Create student
    student, created = User.objects.get_or_create(
        phone='0912345678',  # Use a valid phone number
        defaults={
            'first_name': 'Alice',
            'middle_name': 'B',
            'last_name': 'Johnson',
            'user_type': 'student',
            'is_active': True
        }
    )
    print(f"Student: {student}")
    
    # Create student profile with interests
    # First, get or create University and StudyField instances
    university, _ = University.objects.get_or_create(name="Damascus University")
    study_field, _ = StudyField.objects.get_or_create(name="Computer Science")
    
    profile, created = Profile.objects.get_or_create(
        user=student,
        defaults={
            'academic_status': 'undergraduate',
            'university': university,
            'studyfield': study_field
        }
    )
    
    # Add some interests to the student
    programming_interest, _ = Interest.objects.get_or_create(name='Programming')
    ProfileInterest.objects.get_or_create(
        profile=profile,
        interest=programming_interest,
        defaults={'intensity': 5}
    )
    
    return {
        'department': dept,
        'course_type': course_type,
        'course': course,
        'hall': hall,
        'schedule_slot': schedule_slot,
        'teacher': teacher,
        'student': student
    }

def create_quiz_with_questions(test_data):
    """Create a quiz with questions tied to a schedule slot"""
    print("\nCreating quiz with questions...")
    
    # Create quiz tied to schedule slot
    quiz, created = Quiz.objects.get_or_create(
        title="Python Basics Quiz",
        defaults={
            'description': 'Test your knowledge of Python programming basics',
            'course': test_data['course'],
            'schedule_slot': test_data['schedule_slot'],
            'time_limit_minutes': 30,
            'passing_score': 70,
            'max_attempts': 3,
            'is_active': True
        }
    )
    print(f"Quiz: {quiz}")
    
    # Create questions
    questions_data = [
        {
            'text': 'What is the correct way to create a function in Python?',
            'question_type': 'multiple_choice',
            'points': 2,
            'order': 1,
            'choices': [
                {'text': 'function myFunction():', 'is_correct': False, 'order': 1},
                {'text': 'def myFunction():', 'is_correct': True, 'order': 2},
                {'text': 'create myFunction():', 'is_correct': False, 'order': 3},
                {'text': 'func myFunction():', 'is_correct': False, 'order': 4},
            ]
        },
        {
            'text': 'Python is an interpreted language.',
            'question_type': 'true_false',
            'points': 1,
            'order': 2,
            'choices': [
                {'text': 'True', 'is_correct': True, 'order': 1},
                {'text': 'False', 'is_correct': False, 'order': 2},
            ]
        },
        {
            'text': 'What is the output of print(2 + "2")?',
            'question_type': 'multiple_choice',
            'points': 2,
            'order': 3,
            'choices': [
                {'text': '4', 'is_correct': False, 'order': 1},
                {'text': '22', 'is_correct': False, 'order': 2},
                {'text': 'TypeError', 'is_correct': True, 'order': 3},
                {'text': 'None', 'is_correct': False, 'order': 4},
            ]
        },
        {
            'text': 'Explain what a list comprehension is in Python.',
            'question_type': 'essay',
            'points': 5,
            'order': 4,
            'choices': []
        }
    ]
    
    for q_data in questions_data:
        choices_data = q_data.pop('choices', [])
        question, created = Question.objects.get_or_create(
            quiz=quiz,
            text=q_data['text'],
            defaults=q_data
        )
        print(f"Question: {question.text[:50]}...")
        
        # Create choices for the question
        for c_data in choices_data:
            choice, created = Choice.objects.get_or_create(
                question=question,
                text=c_data['text'],
                defaults=c_data
            )
            print(f"  Choice: {choice.text} (Correct: {choice.is_correct})")
    
    return quiz

def demonstrate_quiz_functionality(quiz, student):
    """Demonstrate quiz functionality"""
    print(f"\nDemonstrating quiz functionality for student: {student.get_full_name()}")
    
    # Check quiz availability
    is_available, message = quiz.is_available_for_user(student)
    print(f"Quiz available: {is_available}")
    print(f"Message: {message}")
    
    if not is_available:
        print("Quiz is not available. Creating enrollment first...")
        
        # Create enrollment for the student
        from courses.models import Enrollment
        enrollment, created = Enrollment.objects.get_or_create(
            student=student,
            course=quiz.course,
            schedule_slot=quiz.schedule_slot,  # Pass the schedule slot
            defaults={
                'first_name': student.first_name,
                'middle_name': student.middle_name,
                'last_name': student.last_name,
                'phone': student.phone,
                'status': 'active',
                'payment_status': 'paid',
                'amount_paid': quiz.course.price,
                'payment_method': 'ewallet'
            }
        )
        print(f"Enrollment created: {enrollment}")
        
        # Check availability again
        is_available, message = quiz.is_available_for_user(student)
        print(f"Quiz available after enrollment: {is_available}")
        print(f"Message: {message}")
    
    if is_available:
        # Start quiz attempt
        print("\nStarting quiz attempt...")
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            user=student,
            status='in_progress'
        )
        print(f"Attempt started: {attempt}")
        
        # Answer questions
        print("\nAnswering questions...")
        for question in quiz.questions.all():
            print(f"\nQuestion: {question.text}")
            
            if question.question_type in ['multiple_choice', 'true_false']:
                # Get correct answers
                correct_choices = question.get_correct_answers()
                print(f"Correct answers: {[c.text for c in correct_choices]}")
                
                # Create answer with correct choices
                answer = QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question
                )
                answer.selected_choices.set(correct_choices)
                answer.calculate_points()
                print(f"Answer created with {answer.points_earned} points")
                
            elif question.question_type == 'essay':
                # Create essay answer
                answer = QuizAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    text_answer="A list comprehension is a concise way to create lists in Python. It provides a more readable and efficient way to create lists compared to using loops."
                )
                print(f"Essay answer created (requires manual grading)")
        
        # Complete the attempt
        print("\nCompleting quiz attempt...")
        attempt.status = 'completed'
        attempt.completed_at = datetime.now()
        attempt.calculate_score()
        attempt.save()
        
        print(f"Quiz completed!")
        print(f"Score: {attempt.score}%")
        print(f"Total points: {attempt.total_points}")
        print(f"Earned points: {attempt.earned_points}")
        print(f"Passed: {attempt.passed}")
        
        # Show detailed results
        print("\nDetailed results:")
        for answer in attempt.answers.all():
            print(f"Question: {answer.question.text[:50]}...")
            print(f"  Points earned: {answer.points_earned}")
            print(f"  Is correct: {answer.is_correct}")
            if answer.text_answer:
                print(f"  Text answer: {answer.text_answer[:100]}...")

def show_quiz_statistics(quiz):
    """Show quiz statistics"""
    print(f"\nQuiz Statistics for: {quiz.title}")
    print("=" * 50)
    
    attempts = quiz.attempts.filter(status='completed')
    
    stats = {
        'total_attempts': attempts.count(),
        'unique_students': attempts.values('user').distinct().count(),
        'average_score': attempts.aggregate(avg_score=django.db.models.Avg('score'))['avg_score'] or 0,
        'pass_rate': 0
    }
    
    if stats['total_attempts'] > 0:
        passed_attempts = attempts.filter(passed=True).count()
        stats['pass_rate'] = (passed_attempts / stats['total_attempts']) * 100
    
    print(f"Total attempts: {stats['total_attempts']}")
    print(f"Unique students: {stats['unique_students']}")
    print(f"Average score: {stats['average_score']:.2f}%")
    print(f"Pass rate: {stats['pass_rate']:.2f}%")
    
    # Score distribution
    print("\nScore distribution:")
    score_ranges = [
        ('0-50', 0, 50),
        ('51-70', 50, 70),
        ('71-85', 70, 85),
        ('86-100', 85, 100)
    ]
    
    for label, min_score, max_score in score_ranges:
        count = attempts.filter(score__gt=min_score, score__lte=max_score).count()
        print(f"  {label}: {count} attempts")

def main():
    """Main function to run the quiz system test"""
    print("Quiz System Test")
    print("=" * 50)
    
    try:
        # Create test data
        test_data = create_test_data()
        
        # Create quiz with questions
        quiz = create_quiz_with_questions(test_data)
        
        # Demonstrate functionality
        demonstrate_quiz_functionality(quiz, test_data['student'])
        
        # Show statistics
        show_quiz_statistics(quiz)
        
        print("\n" + "=" * 50)
        print("Quiz system test completed successfully!")
        print("\nKey Features Demonstrated:")
        print("- Quiz creation tied to schedule slots")
        print("- Multiple question types (multiple choice, true/false, essay)")
        print("- Automatic scoring for objective questions")
        print("- Manual grading capability for essay questions")
        print("- Time limits and attempt tracking")
        print("- Availability checking based on enrollment")
        print("- Comprehensive statistics and reporting")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 