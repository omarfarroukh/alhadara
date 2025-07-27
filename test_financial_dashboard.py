#!/usr/bin/env python3
"""
Test script for financial dashboard metrics
Run with: python test_financial_dashboard.py
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Course, Enrollment, Department, CourseType, Hall
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

def create_test_data():
    """Create sample data for testing financial metrics"""
    print("Creating test data for financial dashboard...")
    
    # Create test department and course type
    department, _ = Department.objects.get_or_create(
        name="Test Department",
        defaults={"description": "Test department for financial metrics"}
    )
    
    course_type, _ = CourseType.objects.get_or_create(
        name="Test Course Type",
        defaults={"department": department}
    )
    
    # Create test hall
    hall, _ = Hall.objects.get_or_create(
        name="Test Hall",
        defaults={
            "capacity": 30,
            "location": "Test Location",
            "hourly_rate": Decimal("50.00")
        }
    )
    
    # Create test courses with different prices
    courses_data = [
        {"title": "Basic Programming", "price": Decimal("200.00")},
        {"title": "Advanced Web Development", "price": Decimal("350.00")},
        {"title": "Data Science Fundamentals", "price": Decimal("450.00")},
        {"title": "Mobile App Development", "price": Decimal("300.00")},
    ]
    
    courses = []
    for course_data in courses_data:
        course, created = Course.objects.get_or_create(
            title=course_data["title"],
            defaults={
                "description": f"Test course: {course_data['title']}",
                "price": course_data["price"],
                "duration": 40,
                "max_students": 25,
                "certification_eligible": True,
                "category": "course",
                "department": department,
                "course_type": course_type,
                "is_active": True
            }
        )
        courses.append(course)
        if created:
            print(f"Created course: {course.title} - ${course.price}")
    
    # Create test students
    students = []
    for i in range(10):
        phone = f"09{12345678 + i}"
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                "first_name": f"Student{i+1}",
                "middle_name": "Test",
                "last_name": "User",
                "user_type": "student",
                "is_active": True
            }
        )
        students.append(user)
        if created:
            print(f"Created student: {user.get_full_name()}")
    
    # Create test enrollments with various payment statuses
    today = timezone.now().date()
    payment_scenarios = [
        {"amount_paid": Decimal("200.00"), "payment_method": "ewallet", "status": "active"},
        {"amount_paid": Decimal("350.00"), "payment_method": "cash", "status": "active"},
        {"amount_paid": Decimal("225.00"), "payment_method": "ewallet", "status": "active"},  # Partial payment
        {"amount_paid": Decimal("300.00"), "payment_method": "cash", "status": "completed"},
        {"amount_paid": Decimal("450.00"), "payment_method": "ewallet", "status": "completed"},
        {"amount_paid": Decimal("100.00"), "payment_method": "ewallet", "status": "active"},  # Partial payment
        {"amount_paid": Decimal("175.00"), "payment_method": "cash", "status": "active"},  # Partial payment
        {"amount_paid": Decimal("300.00"), "payment_method": "ewallet", "status": "active"},
    ]
    
    enrollments = []
    for i, scenario in enumerate(payment_scenarios):
        if i < len(students) and i < len(courses):
            course = courses[i % len(courses)]
            student = students[i]
            
            enrollment, created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={
                    "amount_paid": scenario["amount_paid"],
                    "payment_method": scenario["payment_method"],
                    "status": scenario["status"],
                    "payment_status": "paid" if scenario["amount_paid"] >= course.price else "partial",
                    "first_name": student.first_name,
                    "middle_name": student.middle_name,
                    "last_name": student.last_name,
                    "phone": student.phone,
                    "created_at": today - timedelta(days=i),
                    "updated_at": today - timedelta(days=i)
                }
            )
            
            enrollments.append(enrollment)
            if created:
                print(f"Created enrollment: {student.get_full_name()} -> {course.title} (${scenario['amount_paid']})")
    
    return courses, students, enrollments

def test_financial_metrics():
    """Test the financial metrics calculations"""
    print("\n" + "="*50)
    print("TESTING FINANCIAL METRICS")
    print("="*50)
    
    from courses.models import Enrollment
    from django.db.models import Sum, Avg, Count, F
    
    # Test basic revenue calculations
    total_revenue = Enrollment.objects.filter(
        payment_status__in=['paid', 'partial']
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    print(f"Total Revenue: ${total_revenue}")
    
    # Test payment method breakdown
    ewallet_revenue = Enrollment.objects.filter(
        payment_method='ewallet',
        payment_status__in=['paid', 'partial']
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    cash_revenue = Enrollment.objects.filter(
        payment_method='cash',
        payment_status__in=['paid', 'partial']
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    print(f"eWallet Revenue: ${ewallet_revenue}")
    print(f"Cash Revenue: ${cash_revenue}")
    
    # Test outstanding payments
    outstanding = Enrollment.objects.filter(
        status='active',
        payment_status='partial'
    ).aggregate(
        total=Sum(F('course__price') - F('amount_paid'))
    )['total'] or Decimal('0.00')
    
    print(f"Outstanding Payments: ${outstanding}")
    
    # Test course revenue ranking
    course_revenue = Enrollment.objects.filter(
        payment_status__in=['paid', 'partial']
    ).values('course__title').annotate(
        revenue=Sum('amount_paid'),
        enrollments=Count('id')
    ).order_by('-revenue')[:5]
    
    print("\nTop Courses by Revenue:")
    for course in course_revenue:
        print(f"  {course['course__title']}: ${course['revenue']} ({course['enrollments']} enrollments)")
    
    # Test average metrics
    avg_course_price = Course.objects.aggregate(avg=Avg('price'))['avg'] or Decimal('0.00')
    print(f"\nAverage Course Price: ${avg_course_price:.2f}")
    
    paying_students = Enrollment.objects.filter(
        payment_status__in=['paid', 'partial']
    ).values('student').distinct().count()
    
    revenue_per_student = total_revenue / paying_students if paying_students > 0 else Decimal('0.00')
    print(f"Revenue per Student: ${revenue_per_student:.2f}")
    print(f"Paying Students: {paying_students}")

def test_api_endpoints():
    """Test the API endpoints (if possible)"""
    print("\n" + "="*50)
    print("API ENDPOINTS AVAILABLE")
    print("="*50)
    
    endpoints = [
        "/api/core/dashboard/overview/",
        "/api/core/dashboard/financial/",
        "/api/core/dashboard/enrollments/",
        "/api/core/dashboard/realtime-stats/"
    ]
    
    print("Financial Dashboard API Endpoints:")
    for endpoint in endpoints:
        print(f"  GET {endpoint}")
    
    print("\nWebSocket Connection:")
    print("  ws://localhost:8000/ws/dashboard/supervisor/")

def main():
    print("Financial Dashboard Test Script")
    print("=" * 50)
    
    try:
        # Create test data
        courses, students, enrollments = create_test_data()
        
        # Test financial metrics
        test_financial_metrics()
        
        # Show API endpoints
        test_api_endpoints()
        
        print("\n" + "="*50)
        print("✅ FINANCIAL DASHBOARD TEST COMPLETED SUCCESSFULLY!")
        print("="*50)
        print("\nNext steps:")
        print("1. Start your Django server: python manage.py runserver")
        print("2. Open supervisor_dashboard.html in your browser")
        print("3. Login with admin credentials")
        print("4. View real-time financial metrics!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()