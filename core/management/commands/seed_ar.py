import random
from datetime import time, date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.hashers import make_password
from faker import Faker

# Import all necessary models from your apps
from core.models import (
    User, Profile, Interest, University, StudyField,
    SecurityQuestion, SecurityAnswer
)
from courses.models import (
    Department, CourseType, Course, Enrollment, ScheduleSlot, Hall, HallService
)

# --- CONFIGURATION ---
NUM_TEACHERS = 20
NUM_RECEPTION = 2
NUM_STUDENTS = 100
NUM_DEPARTMENTS = 5
NUM_COURSE_TYPES_PER_DEPT = 5
NUM_COURSES_PER_TYPE = 3
NUM_SLOTS_PER_COURSE = 2
NUM_HALLS = 20
NUM_HALL_SERVICES = 20
NUM_INTERESTS = 100
NUM_UNIVERSITIES = 10
NUM_STUDY_FIELDS = 30

# --- ARABIC DATA SAMPLES ---
DEPARTMENTS_DATA = [
    "قسم اللغات والآداب",
    "قسم تكنولوجيا المعلومات والهندسة",
    "قسم إدارة الأعمال والمحاسبة",
    "قسم الفنون والتصميم",
    "قسم العلوم الصحية والطبية"
]

UNIVERSITIES_DATA = [
    "جامعة دمشق",
    "جامعة حلب",
    "جامعة تشرين",
    "جامعة البعث",
    "الجامعة الافتراضية السورية",
    "جامعة القلمون الخاصة",
    "الجامعة الدولية الخاصة للعلوم والتكنولوجيا",
    "جامعة اليرموك الخاصة",
    "جامعة قرطبة الخاصة",
    "المعهد العالي للعلوم التطبيقية والتكنولوجيا"
]

STUDY_FIELDS_DATA = [
    "هندسة المعلوماتية", "الطب البشري", "طب الأسنان", "الصيدلة", "الهندسة المعمارية",
    "الهندسة المدنية", "الأدب الإنجليزي", "الأدب الفرنسي", "إدارة الأعمال", "المحاسبة",
    "التسويق", "الحقوق", "الاقتصاد", "العلوم السياسية", "التصميم الجرافيكي",
    "التصميم الداخلي", "التمريض", "العلاج الفيزيائي", "الرياضيات", "الفيزياء",
    "الكيمياء", "علم الأحياء", "التاريخ", "الجغرافيا", "علم الاجتماع",
    "الفلسفة", "الإعلام", "هندسة الميكاترونكس", "هندسة الاتصالات", "الترجمة"
]

SECURITY_QUESTIONS_DATA = [
    ("ما هو اسم أفضل صديق لك في طفولتك؟", 'ar'),
    ("ما هو اسم أول حيوان أليف لك؟", 'ar'),
    ("في أي مدينة ولد والدك؟", 'ar'),
    ("ما هو اسم معلمك المفضل؟", 'ar'),
    ("ما هو طبقك المفضل؟", 'ar')
]


class Command(BaseCommand):
    help = "Seeds the database with realistic Arabic data for testing and presentation."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clears existing data (Users, Courses, Profiles, etc.) before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Database Seeding Process ---"))
        
        if options['clear']:
            self._clear_data()

        self._create_data()
        
        self.stdout.write(self.style.SUCCESS("--- Database Seeding Completed Successfully! ---"))

    def _clear_data(self):
        self.stdout.write(self.style.WARNING("Clearing existing data..."))
        # Delete in an order that respects dependencies
        Enrollment.objects.all().delete() # Assuming Enrollment model exists
        ScheduleSlot.objects.all().delete()
        Course.objects.all().delete()
        CourseType.objects.all().delete()
        Department.objects.all().delete()
        Profile.objects.all().delete()
        SecurityAnswer.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Hall.objects.all().delete()
        HallService.objects.all().delete()
        Interest.objects.all().delete()
        University.objects.all().delete()
        StudyField.objects.all().delete()
        SecurityQuestion.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Data cleared."))


    def _create_data(self):
        faker = Faker('ar_SA')

        # 1. Create Independent Data
        self.stdout.write(self.style.NOTICE("Creating Interests, Universities, Study Fields, Halls, and Security Questions..."))
        
        unique_interest_names = set()
        while len(unique_interest_names) < NUM_INTERESTS:
            unique_interest_names.add(faker.word())
        interests = [Interest(name=name, category=random.choice(['academic', 'hobby', 'professional'])) for name in unique_interest_names]
        Interest.objects.bulk_create(interests)

        universities = [University(name=name) for name in UNIVERSITIES_DATA]
        University.objects.bulk_create(universities)

        study_fields = [StudyField(name=name) for name in STUDY_FIELDS_DATA]
        StudyField.objects.bulk_create(study_fields)
        
        security_questions = [SecurityQuestion(question_text=q[0], language=q[1]) for q in SECURITY_QUESTIONS_DATA]
        SecurityQuestion.objects.bulk_create(security_questions)

        unique_service_names = set()
        while len(unique_service_names) < NUM_HALL_SERVICES:
            unique_service_names.add(f"خدمة {faker.word()}")
        hall_services = [HallService(name=name, price=Decimal(random.randint(1000, 5000))) for name in unique_service_names]
        HallService.objects.bulk_create(hall_services)

        unique_hall_names = set()
        while len(unique_hall_names) < NUM_HALLS:
            unique_hall_names.add(f"قاعة {faker.city()}")
        halls = [Hall(name=name, capacity=random.randint(10, 50), location=faker.address(), hourly_rate=Decimal(random.randint(5000, 20000))) for name in unique_hall_names]
        Hall.objects.bulk_create(halls)
        
        # 2. Create Users
        self.stdout.write(self.style.NOTICE("Creating Users (Admin, Teachers, Reception, Students)..."))
        
        # Superuser
        admin, _ = User.objects.get_or_create(
            phone='0911111111',
            defaults={
                'first_name': 'Admin',
                'middle_name': 'User',
                'last_name': 'System',
                'user_type': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        admin.set_password('Admin@123')
        admin.save()
        
        # Teachers
        teachers = []
        for i in range(NUM_TEACHERS):
            phone = f"092{i:07d}"
            teacher = User.objects.create_user(
                phone=phone,
                first_name=faker.first_name(),
                middle_name=faker.first_name(),
                last_name=faker.last_name(),
                password='Teacher@123',
                user_type='teacher'
            )
            teachers.append(teacher)
            
        # Reception
        reception_users = []
        for i in range(NUM_RECEPTION):
            phone = f"093{i:07d}"
            reception = User.objects.create_user(
                phone=phone,
                first_name=faker.first_name(),
                middle_name=faker.first_name(),
                last_name=faker.last_name(),
                password='Reception@123',
                user_type='reception'
            )
            reception_users.append(reception)

        # Students
        students = []
        for i in range(NUM_STUDENTS):
            phone = f"094{i:07d}"
            student = User.objects.create_user(
                phone=phone,
                first_name=faker.first_name(),
                middle_name=faker.first_name(),
                last_name=faker.last_name(),
                password='Student@123',
                user_type='student'
            )
            students.append(student)

        # 3. Create Course Structure
        self.stdout.write(self.style.NOTICE("Creating Departments, Course Types, Courses, and Schedule Slots..."))
        all_courses = []
        # Use a set to track (title, department_id) pairs to ensure uniqueness
        created_course_titles = set()

        for dept_name in DEPARTMENTS_DATA:
            department = Department.objects.create(name=dept_name, description=faker.paragraph(nb_sentences=2))
            
            # Keep track of unique course types per department
            created_course_type_names = set()
            for _ in range(NUM_COURSE_TYPES_PER_DEPT):
                course_type_name = ""
                while True:
                    course_type_name = f"نوع كورس - {faker.word()} {faker.word()}"
                    if course_type_name not in created_course_type_names:
                        created_course_type_names.add(course_type_name)
                        break
                course_type = CourseType.objects.create(department=department, name=course_type_name)

                for _ in range(NUM_COURSES_PER_TYPE):
                    course_title = ""
                    # Loop until a unique title for this department is found
                    while True:
                        course_title = f"كورس {faker.word()} في {department.name}"
                        if (course_title, department.id) not in created_course_titles:
                            created_course_titles.add((course_title, department.id))
                            break
                    
                    course = Course.objects.create(
                        department=department,
                        course_type=course_type,
                        title=course_title, # Use the guaranteed unique title
                        description=faker.paragraph(nb_sentences=5),
                        price=Decimal(random.randint(100000, 500000)),
                        duration=random.randint(20, 60),
                        max_students=random.randint(10, 25),
                        category=random.choice(['course', 'workshop'])
                    )
                    all_courses.append(course)
        
        # Create Schedule Slots for each course
        halls_list = list(Hall.objects.all())
        days = ['sat', 'sun', 'mon', 'tue', 'wed', 'thu', 'fri']
        for course in all_courses:
            for _ in range(NUM_SLOTS_PER_COURSE):
                start_hour = random.randint(8, 18)
                ScheduleSlot.objects.create(
                    course=course,
                    hall=random.choice(halls_list),
                    teacher=random.choice(teachers),
                    days_of_week=random.sample(days, k=random.randint(2, 3)),
                    start_time=time(hour=start_hour, minute=0),
                    end_time=time(hour=start_hour + 2, minute=0),
                    valid_from=date.today() - timedelta(days=random.randint(0, 30)),
                    valid_until=date.today() + timedelta(days=random.randint(30, 90)),
                )
        
        # 4. Create Student Profiles
        self.stdout.write(self.style.NOTICE("Creating Student Profiles..."))
        interests_list = list(Interest.objects.all())
        universities_list = list(University.objects.all())
        study_fields_list = list(StudyField.objects.all())
        for student in students:
            profile = Profile.objects.create(
                user=student,
                birth_date=faker.date_of_birth(minimum_age=18, maximum_age=30),
                gender=random.choice(['male', 'female']),
                address=faker.address(),
                academic_status='undergraduate',
                university=random.choice(universities_list),
                studyfield=random.choice(study_fields_list)
            )
            # Use ProfileInterest through model for intensity
            interests_to_add = random.sample(interests_list, k=random.randint(3, 8))
            for interest in interests_to_add:
                profile.profileinterest_set.create(interest=interest, intensity=random.randint(1, 5))

        # 5. Create Security Answers for all users
        self.stdout.write(self.style.NOTICE("Creating Security Answers..."))
        all_users = [admin] + teachers + reception_users + students
        sec_questions_list = list(SecurityQuestion.objects.all())
        for user in all_users:
            question = random.choice(sec_questions_list)
            SecurityAnswer.objects.get_or_create(
                user=user,
                question=question,
                defaults={'answer_hash': make_password(faker.word())}
            )