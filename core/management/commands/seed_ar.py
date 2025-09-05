import random
from datetime import time, date, timedelta, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

# Import all necessary models
from core.models import User, Profile, Interest, University, StudyField, SecurityQuestion
from courses.models import Department, CourseType, Course, ScheduleSlot, CourseTypeTag, Enrollment, Hall, HallService
from lessons.models import Lesson, Homework, Attendance
from quiz.models import Quiz
from entranceexam.models import EntranceExam, Language, LanguageLevel

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

# --- CURATED ARABIC DATA SAMPLES ---
DEPARTMENTS_DATA = ["قسم اللغات والآداب", "قسم تكنولوجيا المعلومات والهندسة", "قسم إدارة الأعمال والمحاسبة", "قسم الفنون والتصميم", "قسم العلوم الإنسانية"]
UNIVERSITIES_DATA = ["جامعة دمشق", "جامعة حلب", "جامعة تشرين", "جامعة البعث", "الجامعة الافتراضية السورية", "جامعة القلمون الخاصة", "الجامعة العربية الدولية", "جامعة اليرموك الخاصة", "جامعة الأندلس الخاصة", "المعهد العالي لإدارة الأعمال"]
STUDY_FIELDS_DATA = ["هندسة المعلوماتية", "الطب البشري", "طب الأسنان", "الصيدلة", "الهندسة المعمارية", "الهندسة المدنية", "الأدب الإنجليزي", "الأدب الفرنسي", "إدارة الأعمال", "المحاسبة", "التسويق", "الحقوق", "الاقتصاد", "العلوم السياسية", "التصميم الغرافيكي", "التصميم الداخلي", "التمريض", "العلاج الفيزيائي", "الرياضيات", "الفيزياء", "الكيمياء", "علم الأحياء", "التاريخ", "الجغرافيا", "علم الاجتماع", "الفلسفة", "الإعلام", "هندسة الميكاترونكس", "هندسة الاتصالات", "الترجمة"]
SECURITY_QUESTIONS_DATA = ["ما هو اسم أفضل صديق لك في طفولتك؟", "ما هو اسم أول حيوان أليف لك؟", "في أي مدينة ولد والدك؟", "ما هو اسم معلمك المفضل؟", "ما هو طبقك المفضل؟"]
INTERESTS_DATA = ["القراءة", "البرمجة", "كرة القدم", "السفر", "التصوير الفوتوغرافي", "الرسم", "الموسيقى", "السينما", "التطوع", "تعلم اللغات", "ريادة الأعمال", "الطبخ", "التاريخ", "الفلك", "السياسة", "الاقتصاد", "الشطرنج", "ألعاب الفيديو", "التصميم", "الكتابة", "العلوم", "التكنولوجيا", "الهندسة", "الرياضيات", "الفيزياء", "الكيمياء", "الأحياء", "الطب", "الصيدلة", "طب الأسنان", "التمريض", "العلاج الفيزيائي", "القانون", "المحاسبة", "إدارة الأعمال", "التسويق", "الإعلام", "الفلسفة", "علم النفس", "علم الاجتماع", "الأنثروبولوجيا", "الآثار", "الجغرافيا", "الجيولوجيا", "البيئة", "الزراعة", "العمارة", "الهندسة المدنية", "الهندسة الميكانيكية", "الهندسة الكهربائية", "هندسة الحاسوب", "هندسة البرمجيات", "علوم الحاسوب", "نظم المعلومات", "الشبكات", "الأمن السيبراني", "الذكاء الاصطناعي", "تعلم الآلة", "البيانات الضخمة", "الحوسبة السحابية", "إنترنت الأشياء", "الروبوتات", "الواقع الافتراضي", "الواقع المعزز", "تطوير الويب", "تطوير تطبيقات الهاتف المحمول", "تصميم واجهات المستخدم", "تجربة المستخدم", "التجارة الإلكترونية", "التسويق الرقمي", "وسائل التواصل الاجتماعي", "تحسين محركات البحث", "تحليل البيانات", "إدارة المشاريع", "الموارد البشرية", "المالية", "الاستثمار", "العقارات", "السياحة", "الفندقة", "الطيران", "النقل", "اللوجستيات", "التصنيع", "الطاقة", "التعدين", "البناء", "التجزئة", "الجملة", "التعليم", "الصحة", "الترفيه", "الفن", "الثقافة", "الرياضة"]
COURSE_SUBJECTS_DATA = ["البرمجة بلغة بايثون", "التصميم الغرافيكي", "التسويق الرقمي", "اللغة الإنجليزية للمبتدئين", "إدارة المشاريع الاحترافية", "المحاسبة المالية", "تحليل البيانات باستخدام إكسل", "مقدمة في الذكاء الاصطناعي", "أساسيات الأمن السيبراني", "التصوير الفوتوغرافي", "صناعة المحتوى الرقمي", "اللغة الألمانية", "إدارة الموارد البشرية", "الترجمة القانونية", "الرسم الزيتي", "تطوير تطبيقات الويب", "مهارات العرض والتقديم", "كتابة السيرة الذاتية"]

class Command(BaseCommand):
    help = "Seeds the database with rich, purely Arabic data."

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clears relevant data before seeding.')

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- بدء عملية ملء قاعدة البيانات ---"))
        if options['clear']: self._clear_data()
        self._create_data()
        self.stdout.write(self.style.SUCCESS("--- اكتملت عملية ملء قاعدة البيانات بنجاح! ---"))

    def _clear_data(self):
        self.stdout.write(self.style.WARNING("... يتم حذف البيانات الحالية ..."))
        # Delete in an order that respects dependencies
        Attendance.objects.all().delete()
        Homework.objects.all().delete()
        Lesson.objects.all().delete()
        Quiz.objects.all().delete()
        Enrollment.objects.all().delete()
        CourseTypeTag.objects.all().delete()
        ScheduleSlot.objects.all().delete()
        Course.objects.all().delete()
        CourseType.objects.all().delete()
        Department.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Hall.objects.all().delete()
        HallService.objects.all().delete()
        Interest.objects.all().delete()
        University.objects.all().delete()
        StudyField.objects.all().delete()
        SecurityQuestion.objects.all().delete()
        EntranceExam.objects.all().delete()
        Language.objects.all().delete()
        LanguageLevel.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("... تم حذف البيانات."))

    def _create_data(self):
        faker = Faker('ar_EG')

        # 1. Independent Data
        self.stdout.write(self.style.NOTICE("... إنشاء الاهتمامات، الجامعات، مجالات الدراسة، القاعات، والأسئلة الأمنية ..."))
        
        num_interests_to_create = min(NUM_INTERESTS, len(INTERESTS_DATA))
        interest_names = random.sample(INTERESTS_DATA, num_interests_to_create)
        interests = [Interest(name=name, category=random.choice(['academic', 'hobby', 'professional'])) for name in interest_names]
        Interest.objects.bulk_create(interests)

        universities = [University(name=name) for name in UNIVERSITIES_DATA]
        University.objects.bulk_create(universities)

        study_fields = [StudyField(name=name) for name in STUDY_FIELDS_DATA]
        StudyField.objects.bulk_create(study_fields)
        
        security_questions = [SecurityQuestion(question_text=q, language='ar') for q in SECURITY_QUESTIONS_DATA]
        SecurityQuestion.objects.bulk_create(security_questions)

        unique_service_names = set()
        while len(unique_service_names) < NUM_HALL_SERVICES:
            unique_service_names.add(f"خدمة {faker.word()}")
        hall_services = [HallService(name=name, price=Decimal(random.randint(10, 50) * 1000)) for name in unique_service_names]
        HallService.objects.bulk_create(hall_services)

        unique_hall_names = set()
        while len(unique_hall_names) < NUM_HALLS:
            unique_hall_names.add(f"قاعة {faker.city()}")
        halls = [Hall(name=name, capacity=random.randint(10, 50), location=faker.address(), hourly_rate=Decimal(random.randint(5, 20) * 10000)) for name in unique_hall_names]
        Hall.objects.bulk_create(halls)

        # 2. Users
        self.stdout.write(self.style.NOTICE("... إنشاء المستخدمين (مدير، مدرسين، موظفي استقبال، طلاب) ..."))
        admin, _ = User.objects.get_or_create(phone='0911111111', defaults={'first_name': 'المدير', 'middle_name': 'العام', 'last_name': 'للنظام', 'user_type': 'admin', 'is_staff': True, 'is_superuser': True, 'is_active': True})
        admin.set_password('Admin@123'); admin.save()
        
        teachers = [User.objects.create_user(phone=f"092{i:07d}", first_name=faker.first_name_male(), middle_name=faker.first_name_male(), last_name=faker.last_name(), password='Teacher@123', user_type='teacher') for i in range(NUM_TEACHERS)]
        reception_users = [User.objects.create_user(phone=f"093{i:07d}", first_name=faker.first_name_female(), middle_name=faker.first_name_female(), last_name=faker.last_name(), password='Reception@123', user_type='reception') for i in range(NUM_RECEPTION)]
        students = [User.objects.create_user(phone=f"094{i:07d}", first_name=faker.first_name(), middle_name=faker.first_name(), last_name=faker.last_name(), password='Student@123', user_type='student') for i in range(NUM_STUDENTS)]

        # 3. Profiles
        self.stdout.write(self.style.NOTICE("... إنشاء الملفات الشخصية للطلاب ..."))
        interests_list = list(Interest.objects.all()); universities_list = list(University.objects.all()); study_fields_list = list(StudyField.objects.all())
        for student in students:
            profile = Profile.objects.create(user=student, birth_date=faker.date_of_birth(minimum_age=18, maximum_age=30), gender=random.choice(['male', 'female']), address=faker.address(), academic_status='undergraduate', university=random.choice(universities_list), studyfield=random.choice(study_fields_list))
            for interest in random.sample(interests_list, k=random.randint(3, 8)):
                profile.profileinterest_set.create(interest=interest, intensity=random.randint(1, 5))

        # 4. Course Structure
        self.stdout.write(self.style.NOTICE("... إنشاء الأقسام، أنواع الكورسات، الكورسات، والجداول الزمنية ..."))
        all_courses, all_slots = [], []
        created_course_titles = set()
        study_fields_list_cache = list(StudyField.objects.all())

        for dept_name in DEPARTMENTS_DATA:
            department = Department.objects.create(name=dept_name, description=faker.paragraph(nb_sentences=2))
            subjects_for_dept = random.sample(COURSE_SUBJECTS_DATA, k=min(NUM_COURSE_TYPES_PER_DEPT, len(COURSE_SUBJECTS_DATA)))
            
            for subject in subjects_for_dept:
                course_type_name = f"دورة متخصصة في {subject}"
                course_type, _ = CourseType.objects.get_or_create(name=course_type_name, defaults={'department': department})
                CourseTypeTag.objects.create(course_type=course_type, study_field=random.choice(study_fields_list_cache))
                
                for j in range(NUM_COURSES_PER_TYPE):
                    course_title = f"{subject} - المستوى {['المبتدئ', 'المتوسط', 'المتقدم'][j]}"
                    if (course_title, department.id) not in created_course_titles:
                        created_course_titles.add((course_title, department.id))
                        course = Course.objects.create(department=department, course_type=course_type, title=course_title, description=faker.paragraph(nb_sentences=5), price=Decimal(random.randint(100, 500) * 1000), duration=random.randint(20, 60), max_students=random.randint(10, 25), category=random.choice(['course', 'workshop']))
                        all_courses.append(course)
        
        if not all_courses: raise Exception("FATAL: No courses were created. Seeding cannot continue.")

        halls_list = list(Hall.objects.all()); days = ['sat', 'sun', 'mon', 'tue', 'wed', 'thu']
        for course in all_courses:
            for _ in range(NUM_SLOTS_PER_COURSE):
                start_hour = random.choice([8, 10, 12, 14, 16, 18])
                slot = ScheduleSlot.objects.create(course=course, hall=random.choice(halls_list), teacher=random.choice(teachers), days_of_week=random.sample(days, k=random.randint(2, 3)), start_time=time(hour=start_hour), end_time=time(hour=start_hour + 2), valid_from=date.today() - timedelta(days=random.randint(0, 30)), valid_until=date.today() + timedelta(days=random.randint(30, 90)))
                all_slots.append(slot)
        
        if not all_slots: raise Exception("FATAL: No schedule slots were created. Seeding cannot continue.")
        
        # 5. Enrollments, Lessons, Homework, Attendance, Quizzes
        self.stdout.write(self.style.NOTICE("... إنشاء التسجيلات، الدروس، الواجبات، الحضور، والاختبارات ..."))
        for student in random.sample(students, k=min(int(NUM_STUDENTS * 0.8), len(students))):
            slot = random.choice(all_slots)
            enrollment, created = Enrollment.objects.get_or_create(student=student, course=slot.course, defaults={'schedule_slot': slot, 'payment_method': 'ewallet', 'amount_paid': slot.course.price * Decimal('0.3')})
            if created and enrollment.schedule_slot and enrollment.schedule_slot.valid_until > date.today():
                for i in range(5):
                    lesson_date = slot.valid_from + timedelta(days=i*7)
                    if lesson_date < slot.valid_until:
                        lesson = Lesson.objects.create(course=slot.course, schedule_slot=slot, title=f"الدرس {i+1}: مقدمة في {slot.course.title}", lesson_order=i+1, lesson_date=lesson_date)
                        Attendance.objects.create(enrollment=enrollment, lesson=lesson, teacher=slot.teacher, attendance=random.choice(['present', 'present', 'absent']))
                        if i < 4:
                            Homework.objects.create(lesson=lesson, title=f"واجب الدرس {i+1}", description="الرجاء حل التمارين المرفقة", deadline=timezone.make_aware(datetime.combine(lesson_date + timedelta(days=3), time(23, 59))))
                Quiz.objects.create(course=slot.course, schedule_slot=slot, title=f"اختبار منتصف الفصل لـ {slot.course.title}", time_limit_minutes=45)

        # 6. Entrance Exams
        self.stdout.write(self.style.NOTICE("... إنشاء امتحانات القبول والمستويات ..."))
        Language.objects.all().delete()
        langs = [Language.objects.create(name=name) for name, _ in Language.LANGUAGE_CHOICES]
        levels_data = [('a1', 0, 20), ('a2', 21, 40), ('b1', 41, 60), ('b2', 61, 80), ('c1', 81, 90), ('c2', 91, 100)]
        LanguageLevel.objects.all().delete()
        for l_code, l_min, l_max in levels_data: LanguageLevel.objects.create(level=l_code, min_score=l_min, max_score=l_max)
        for lang in langs:
            EntranceExam.objects.create(language=lang, title=f"امتحان تحديد مستوى اللغة {lang.get_name_display()}", grading_teacher=random.choice(teachers), is_active=True)