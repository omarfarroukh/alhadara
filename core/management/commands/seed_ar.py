# -*- coding: utf-8 -*-
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
    help = 'تعبئة قاعدة البيانات بالبيانات الابتدائية'

    def handle(self, *args, **kwargs):
        self.stdout.write('بدء تعبئة البيانات...')
        self.create_users()
        self.create_security_questions()
        self.create_interests()
        self.create_universities_and_study_fields()
        self.create_deposit_methods()
        self.create_departments_and_course_types()
        self.create_halls()
        self.create_courses()
        self.stdout.write(self.style.SUCCESS('تم تعبئة جميع البيانات بنجاح!'))

    # ------------------------------------------------------------------
    # المستخدمون
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # أسئلة الأمان
    # ------------------------------------------------------------------
    def create_security_questions(self):
        self.stdout.write('إنشاء أسئلة الأمان...')
        questions = [
            {'text': 'ما هو اسم والدتك قبل الزواج؟', 'language': 'ar'},
            {'text': 'ما هو اسم حيوانك الأليف الأول؟', 'language': 'ar'},
            {'text': 'في أي مدينة وُلدت؟', 'language': 'ar'},
            {'text': 'ما هو كتابك المفضل؟', 'language': 'ar'},
            {'text': 'ما هو لقبك في الطفولة؟', 'language': 'ar'},
            {'text': 'ما هو اسم والدتك قبل الزواج؟', 'language': 'ar'},
            {'text': 'ما هو اسم حيوانك الأليف الأول؟', 'language': 'ar'},
            {'text': 'في أي مدينة وُلدت؟', 'language': 'ar'},
            {'text': 'ما هو كتابك المفضل؟', 'language': 'ar'},
            {'text': 'ما هو لقبك في الطفولة؟', 'language': 'ar'},
        ]
        for q in questions:
            SecurityQuestion.objects.get_or_create(question_text=q['text'], language=q['language'])
        self.stdout.write('تم إنشاء أسئلة الأمان')

    # ------------------------------------------------------------------
    # الاهتمامات
    # ------------------------------------------------------------------
    def create_interests(self):
        self.stdout.write('إنشاء الاهتمامات...')
        interests = [
            {'name': 'الرياضيات', 'category': 'academic'},
            {'name': 'الفيزياء', 'category': 'academic'},
            {'name': 'علوم الحاسوب', 'category': 'academic'},
            {'name': 'الأدب', 'category': 'academic'},
            {'name': 'التاريخ', 'category': 'academic'},
            {'name': 'التصوير', 'category': 'hobby'},
            {'name': 'الطبخ', 'category': 'hobby'},
            {'name': 'الموسيقى', 'category': 'hobby'},
            {'name': 'الرياضة', 'category': 'hobby'},
            {'name': 'الرسم', 'category': 'hobby'},
            {'name': 'البرمجة', 'category': 'professional'},
            {'name': 'رجال الأعمال', 'category': 'professional'},
            {'name': 'التسويق', 'category': 'professional'},
            {'name': 'التصميم', 'category': 'professional'},
            {'name': 'الإدارة', 'category': 'professional'},
        ]
        for i in interests:
            Interest.objects.get_or_create(name=i['name'], category=i['category'])
        self.stdout.write('تم إنشاء الاهتمامات')

    # ------------------------------------------------------------------
    # الجامعات ومجالات الدراسة
    # ------------------------------------------------------------------
    def create_universities_and_study_fields(self):
        self.stdout.write('إنشاء الجامعات ومجالات الدراسة...')
        universities = [
            'جامعة دمشق',
            'جامعة حلب',
            'جامعة تشرين',
            'جامعة حمص',
            'جامعة اللاذقية',
        ]
        for uni in universities:
            University.objects.get_or_create(name=uni)

        fields = [
            'علوم الحاسوب',
            'الهندسة',
            'الطب',
            'إدارة الأعمال',
            'الحقوق',
            'الأدب',
            'الرياضيات',
            'الفيزياء',
            'الكيمياء',
            'الأحياء',
        ]
        for f in fields:
            StudyField.objects.get_or_create(name=f)
        self.stdout.write('تم إنشاء الجامعات ومجالات الدراسة')

    # ------------------------------------------------------------------
    # طرق الإيداع
    # ------------------------------------------------------------------
    def create_deposit_methods(self):
        self.stdout.write('إنشاء طرق الإيداع...')
        bank = DepositMethod.objects.get_or_create(name='تحويل بنكي', is_active=True)[0]
        BankTransferInfo.objects.get_or_create(
            deposit_method=bank,
            account_name='الهدرة للتعليم',
            account_number='1234567890',
            bank_name='المصرف التجاري السوري',
            iban='SY123456789012345678901234'
        )

        money = DepositMethod.objects.get_or_create(name='تحويل مالي', is_active=True)[0]
        MoneyTransferInfo.objects.get_or_create(
            deposit_method=money,
            company_name='ويسترن يونيون',
            receiver_name='الهدرة للتعليم',
            receiver_phone='0999999999'
        )
        self.stdout.write('تم إنشاء طرق الإيداع')

    # ------------------------------------------------------------------
    # الأقسام وأنواع الدورات
    # ------------------------------------------------------------------
    def create_departments_and_course_types(self):
        self.stdout.write('إنشاء الأقسام وأنواع الدورات...')
        data = [
            {
                'name': 'علوم الحاسوب',
                'description': 'دورات تتعلق بالبرمجة، الخوارزميات، وأنظمة الحاسوب',
                'types': [
                    'لغات البرمجة',
                    'تطوير الويب',
                    'تطوير التطبيقات المحمولة',
                    'علم البيانات',
                    'الذكاء الاصطناعي'
                ]
            },
            {
                'name': 'اللغات',
                'description': 'دورات لتعلم اللغات تشمل الإنجليزية، العربية وغيرها',
                'types': [
                    'اللغة الإنجليزية',
                    'اللغة العربية',
                    'اللغة الفرنسية',
                    'اللغة الألمانية',
                    'اللغة الإسبانية'
                ]
            },
            {
                'name': 'الأعمال',
                'description': 'دورات تتعلق بالأعمال والإدارة',
                'types': [
                    'إدارة الأعمال',
                    'التسويق',
                    'المالية',
                    'ريادة الأعمال',
                    'إدارة المشاريع'
                ]
            }
        ]
        for d in data:
            dept, _ = Department.objects.get_or_create(
                name=d['name'],
                description=d['description']
            )
            for ctype in d['types']:
                CourseType.objects.get_or_create(name=ctype, department=dept)
        self.stdout.write('تم إنشاء الأقسام وأنواع الدورات')

    # ------------------------------------------------------------------
    # القاعات
    # ------------------------------------------------------------------
    def create_halls(self):
        self.stdout.write('إنشاء القاعات...')
        halls = [
            {
                'name': 'القاعة الرئيسية',
                'capacity': 50,
                'location': 'الطابق الأول',
                'hourly_rate': Decimal('50.00')
            },
            {
                'name': 'قاعة المؤتمرات',
                'capacity': 30,
                'location': 'الطابق الثاني',
                'hourly_rate': Decimal('75.00')
            },
            {
                'name': 'الفصل الصغير',
                'capacity': 20,
                'location': 'الطابق الثالث',
                'hourly_rate': Decimal('35.00')
            }
        ]
        for h in halls:
            Hall.objects.get_or_create(name=h['name'], defaults=h)
        self.stdout.write('تم إنشاء القاعات')

    # ------------------------------------------------------------------
    # الدورات
    # ------------------------------------------------------------------
    def create_courses(self):
        self.stdout.write('إنشاء الدورات...')
        for ct in CourseType.objects.all():
            for i in range(5):
                is_workshop = (i == 2)
                data = {
                    'title': f'{ct.name} الدورة {i+1}',
                    'description': f'وصف دورة {ct.name} رقم {i+1}',
                    'price': Decimal('200.00') + (i * Decimal('50.00')),
                    'duration': 20 + (i * 5),
                    'max_students': 15 - (i % 3),
                    'certification_eligible': True,
                    'category': 'ورشة' if is_workshop else 'دورة',
                    'department': ct.department,
                    'course_type': ct
                }
                Course.objects.get_or_create(
                    title=data['title'],
                    department=data['department'],
                    defaults=data
                )
        self.stdout.write('تم إنشاء الدورات')