from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import (
    SecurityQuestion, Interest, University, StudyField,
    Profile, ProfileInterest, DepositMethod, BankTransferInfo,
    MoneyTransferInfo
)
from courses.models import (
    Department, CourseType, Hall, Course, ScheduleSlot
)
from decimal import Decimal
from datetime import datetime, timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with initial data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting to seed data...')
        
        # Create users
        self.create_users()
        
        # Create security questions
        self.create_security_questions()
        
        # Create interests
        self.create_interests()
        
        # Create universities and study fields
        self.create_universities_and_study_fields()
        
        # Create deposit methods and their info
        self.create_deposit_methods()
        
        # Create departments and course types
        self.create_departments_and_course_types()
        
        # Create halls
        self.create_halls()
        
        # Create courses
        self.create_courses()
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded all data!'))

    def create_users(self):
        self.stdout.write('Creating users...')
        
        # Create superuser
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                phone='0999999999',
                first_name='Admin',
                middle_name='User',
                last_name='System',
                password='Admin@123',
                user_type='admin'
            )
            self.stdout.write('Created superuser')

        # Create teachers
        teachers_data = [
            {
                'phone': '0988888888',
                'first_name': 'John',
                'middle_name': 'Smith',
                'last_name': 'Doe',
                'password': 'Teacher@123',
                'user_type': 'teacher'
            },
            {
                'phone': '0977777777',
                'first_name': 'Jane',
                'middle_name': 'Marie',
                'last_name': 'Smith',
                'password': 'Teacher@123',
                'user_type': 'teacher'
            }
        ]
        
        for teacher_data in teachers_data:
            if not User.objects.filter(phone=teacher_data['phone']).exists():
                User.objects.create_user(**teacher_data)
                self.stdout.write(f'Created teacher: {teacher_data["first_name"]}')

        # Create reception
        if not User.objects.filter(user_type='reception').exists():
            User.objects.create_user(
                phone='0966666666',
                first_name='Reception',
                middle_name='Staff',
                last_name='User',
                password='Reception@123',
                user_type='reception'
            )
            self.stdout.write('Created reception user')

        # Create students
        students_data = [
            {
                'phone': '0955555555',
                'first_name': 'Student',
                'middle_name': 'One',
                'last_name': 'User',
                'password': 'Student@123',
                'user_type': 'student'
            },
            {
                'phone': '0944444444',
                'first_name': 'Student',
                'middle_name': 'Two',
                'last_name': 'User',
                'password': 'Student@123',
                'user_type': 'student'
            }
        ]
        
        for student_data in students_data:
            if not User.objects.filter(phone=student_data['phone']).exists():
                User.objects.create_user(**student_data)
                self.stdout.write(f'Created student: {student_data["first_name"]}')

    def create_security_questions(self):
        self.stdout.write('Creating security questions...')
        
        questions = [
            {'text': 'What is your mother\'s maiden name?', 'language': 'en'},
            {'text': 'What was your first pet\'s name?', 'language': 'en'},
            {'text': 'In which city were you born?', 'language': 'en'},
            {'text': 'What is your favorite book?', 'language': 'en'},
            {'text': 'What was your childhood nickname?', 'language': 'en'},
            {'text': 'ما هو اسم والدتك قبل الزواج؟', 'language': 'ar'},
            {'text': 'ما هو اسم حيوانك الأليف الأول؟', 'language': 'ar'},
            {'text': 'في أي مدينة ولدت؟', 'language': 'ar'},
            {'text': 'ما هو كتابك المفضل؟', 'language': 'ar'},
            {'text': 'ما هو لقبك في الطفولة؟', 'language': 'ar'}
        ]
        
        for q in questions:
            SecurityQuestion.objects.get_or_create(
                question_text=q['text'],
                language=q['language']
            )
        self.stdout.write('Created security questions')

    def create_interests(self):
        self.stdout.write('Creating interests...')
        
        interests = [
            # Academic interests
            {'name': 'Mathematics', 'category': 'academic'},
            {'name': 'Physics', 'category': 'academic'},
            {'name': 'Computer Science', 'category': 'academic'},
            {'name': 'Literature', 'category': 'academic'},
            {'name': 'History', 'category': 'academic'},
            
            # Hobby interests
            {'name': 'Photography', 'category': 'hobby'},
            {'name': 'Cooking', 'category': 'hobby'},
            {'name': 'Music', 'category': 'hobby'},
            {'name': 'Sports', 'category': 'hobby'},
            {'name': 'Painting', 'category': 'hobby'},
            
            # Professional interests
            {'name': 'Programming', 'category': 'professional'},
            {'name': 'Business', 'category': 'professional'},
            {'name': 'Marketing', 'category': 'professional'},
            {'name': 'Design', 'category': 'professional'},
            {'name': 'Management', 'category': 'professional'}
        ]
        
        for interest in interests:
            Interest.objects.get_or_create(
                name=interest['name'],
                category=interest['category']
            )
        self.stdout.write('Created interests')

    def create_universities_and_study_fields(self):
        self.stdout.write('Creating universities and study fields...')
        
        # Create universities
        universities = [
            'Damascus University',
            'University of Aleppo',
            'Tishreen University',
            'University of Homs',
            'University of Latakia'
        ]
        
        for uni in universities:
            University.objects.get_or_create(name=uni)
        
        # Create study fields
        study_fields = [
            'Computer Science',
            'Engineering',
            'Medicine',
            'Business Administration',
            'Law',
            'Literature',
            'Mathematics',
            'Physics',
            'Chemistry',
            'Biology'
        ]
        
        for field in study_fields:
            StudyField.objects.get_or_create(name=field)
            
        self.stdout.write('Created universities and study fields')

    def create_deposit_methods(self):
        self.stdout.write('Creating deposit methods...')
        
        # Create bank transfer method
        bank_transfer, _ = DepositMethod.objects.get_or_create(
            name='bank_transfer',
            is_active=True
        )
        
        # Create bank transfer info
        BankTransferInfo.objects.get_or_create(
            deposit_method=bank_transfer,
            account_name='Alhadara Education',
            account_number='1234567890',
            bank_name='Commercial Bank of Syria',
            iban='SY123456789012345678901234'
        )
        
        # Create money transfer method
        money_transfer, _ = DepositMethod.objects.get_or_create(
            name='money_transfer',
            is_active=True
        )
        
        # Create money transfer info
        MoneyTransferInfo.objects.get_or_create(
            deposit_method=money_transfer,
            company_name='Western Union',
            receiver_name='Alhadara Education',
            receiver_phone='0999999999'
        )
        
        self.stdout.write('Created deposit methods and their info')

    def create_departments_and_course_types(self):
        self.stdout.write('Creating departments and course types...')
        
        departments_data = [
            {
                'name': 'Computer Science',
                'description': 'Courses related to programming, algorithms, and computer systems',
                'course_types': [
                    'Programming Languages',
                    'Web Development',
                    'Mobile Development',
                    'Data Science',
                    'Artificial Intelligence'
                ]
            },
            {
                'name': 'Languages',
                'description': 'Language learning courses including English, Arabic, and more',
                'course_types': [
                    'English Language',
                    'Arabic Language',
                    'French Language',
                    'German Language',
                    'Spanish Language'
                ]
            },
            {
                'name': 'Business',
                'description': 'Business and management related courses',
                'course_types': [
                    'Business Management',
                    'Marketing',
                    'Finance',
                    'Entrepreneurship',
                    'Project Management'
                ]
            }
        ]
        
        for dept_data in departments_data:
            department, _ = Department.objects.get_or_create(
                name=dept_data['name'],
                description=dept_data['description']
            )
            
            for course_type_name in dept_data['course_types']:
                CourseType.objects.get_or_create(
                    name=course_type_name,
                    department=department
                )
        
        self.stdout.write('Created departments and course types')

    def create_halls(self):
        self.stdout.write('Creating halls...')
        
        halls_data = [
            {
                'name': 'Main Hall',
                'capacity': 50,
                'location': 'First Floor',
                'hourly_rate': Decimal('50.00')
            },
            {
                'name': 'Conference Room',
                'capacity': 30,
                'location': 'Second Floor',
                'hourly_rate': Decimal('75.00')
            },
            {
                'name': 'Small Classroom',
                'capacity': 20,
                'location': 'Third Floor',
                'hourly_rate': Decimal('35.00')
            }
        ]
        
        for hall_data in halls_data:
            Hall.objects.get_or_create(
                name=hall_data['name'],
                defaults=hall_data
            )
        
        self.stdout.write('Created halls')

    def create_courses(self):
        self.stdout.write('Creating courses...')
        
        # Get all course types
        course_types = CourseType.objects.all()
        
        # Create 5 courses for each course type
        for course_type in course_types:
            for i in range(5):
                is_workshop = i == 2  # Make the third course a workshop
                course_data = {
                    'title': f'{course_type.name} Course {i+1}',
                    'description': f'Description for {course_type.name} Course {i+1}',
                    'price': Decimal('200.00') + (i * Decimal('50.00')),
                    'duration': 20 + (i * 5),
                    'max_students': 15 - (i % 3),
                    'certification_eligible': True,
                    'category': 'workshop' if is_workshop else 'course',
                    'department': course_type.department,
                    'course_type': course_type
                }
                
                Course.objects.get_or_create(
                    title=course_data['title'],
                    department=course_data['department'],
                    defaults=course_data
                )
        
        self.stdout.write('Created courses') 