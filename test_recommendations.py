#!/usr/bin/env python
"""
Test script for the course recommendation system
Run this after setting up the database and seeding data
"""

import os
import django
from datetime import date, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Interest, StudyField, Profile, ProfileInterest, University
from courses.models import Course, CourseType

User = get_user_model()

def test_recommendations():
    """Test the recommendation system"""
    print("🎯 Testing Course Recommendation System\n")
    
    # Create a test student with interests
    student, created = User.objects.get_or_create(
        phone='0999999999',
        defaults={
            'first_name': 'Test',
            'middle_name': 'Student',
            'last_name': 'User',
            'password': 'testpass123',
            'user_type': 'student'
        }
    )
    
    if created:
        print(f"✅ Created test student: {student.get_full_name()}")
    
    # Get or create profile with proper academic status
    try:
        profile = student.profile
        print(f"✅ Found existing profile for {student.get_full_name()}")
    except Profile.DoesNotExist:
        # Create profile with undergraduate status (requires university and study field)
        university, _ = University.objects.get_or_create(name='Damascus University')
        study_field, _ = StudyField.objects.get_or_create(name='Computer Science')
        
        profile = Profile.objects.create(
            user=student,
            academic_status='undergraduate',
            university=university,
            studyfield=study_field
        )
        print(f"✅ Created profile for {student.get_full_name()} (undergraduate)")
    
    # Add interests with different intensities to the student
    interests_with_intensity = [
        ('Programming', 5),      # High intensity
        ('Web Development', 4),  # Medium-high intensity
        ('Mathematics', 3),      # Medium intensity
        ('Design', 2),           # Low-medium intensity
        ('Business', 4),         # Medium-high intensity (added for diversity)
        ('Marketing', 3),        # Medium intensity (added for diversity)
    ]
    
    for interest_name, intensity in interests_with_intensity:
        interest, _ = Interest.objects.get_or_create(name=interest_name)
        ProfileInterest.objects.get_or_create(
            profile=profile,
            interest=interest,
            defaults={'intensity': intensity}
        )
        print(f"✅ Added interest: {interest_name} (intensity: {intensity})")
    
    print(f"📊 Total interests: {len(interests_with_intensity)}")
    
    # Set study field if not already set
    if not profile.studyfield:
        study_field, _ = StudyField.objects.get_or_create(name='Computer Science')
        profile.studyfield = study_field
        profile.save()
        print(f"✅ Set study field: {study_field.name}")
    else:
        print(f"✅ Study field already set: {profile.studyfield.name}")
    
    # Get recommendations
    print("\n🔍 Getting course recommendations...")
    recommended_courses = Course.get_recommended_courses(student, limit=8)
    
    if recommended_courses:
        print(f"\n📚 Found {len(recommended_courses)} recommended courses:")
        
        # Group by course type to show distribution
        course_type_distribution = {}
        for i, course in enumerate(recommended_courses, 1):
            course_type_name = course.course_type.name
            if course_type_name not in course_type_distribution:
                course_type_distribution[course_type_name] = []
            
            course_type_distribution[course_type_name].append(course)
            
            # Check if course has valid schedule slots
            valid_slots = course.schedule_slots.filter(
                valid_from__gte=date.today(),
                valid_from__lte=date.today() + timedelta(days=90)
            ).count()
            
            print(f"  {i}. {course.title}")
            print(f"     Department: {course.department.name}")
            print(f"     Course Type: {course_type_name}")
            print(f"     Price: ${course.price}")
            print(f"     Valid Schedule Slots: {valid_slots}")
            print(f"     Final Score: {getattr(course, 'final_score', 'N/A')}")
            print(f"     Weighted Score: {getattr(course, 'weighted_score', 'N/A')}")
            print(f"     Study Field Bonus: {getattr(course, 'study_field_bonus', 'N/A')}")
            print()
        
        # Show diversification summary
        print("🎯 Diversification Summary:")
        for course_type_name, courses in course_type_distribution.items():
            print(f"   {course_type_name}: {len(courses)} course(s)")
            scores = [getattr(course, 'final_score', 0) for course in courses]
            print(f"     Score range: {min(scores)} - {max(scores)}")
        
        # Show interest count impact
        print(f"\n📈 Interest Count Impact:")
        print(f"   User has {len(interests_with_intensity)} interests")
        if len(interests_with_intensity) >= 8:
            print("   → High diversity mode: Up to 8 course types, more courses per type")
        elif len(interests_with_intensity) >= 5:
            print("   → Medium diversity mode: Up to 6 course types, balanced approach")
        elif len(interests_with_intensity) >= 3:
            print("   → Low-medium diversity mode: Up to 4 course types, focus on top types")
        else:
            print("   → Low diversity mode: Up to 3 course types, focus on best matches")
    else:
        print("❌ No recommendations found. Make sure you have:")
        print("   - Course types with tags (run: python manage.py seed_course_tags)")
        print("   - Courses associated with those course types")
        print("   - Courses with valid schedule slots (starting within next 3 months)")
        print("   - Run: python manage.py seed_data")

def show_course_type_tags():
    """Show all course types and their tags"""
    print("\n🏷️  Course Type Tags:")
    for course_type in CourseType.objects.all():
        tags = course_type.get_tags()
        print(f"\n📖 {course_type.name} ({course_type.department.name}):")
        if tags['interests']:
            print(f"   Interests: {', '.join(tags['interests'])}")
        if tags['study_fields']:
            print(f"   Study Fields: {', '.join(tags['study_fields'])}")

def show_user_interests():
    """Show user interests with intensity"""
    print("\n👤 User Interests with Intensity:")
    try:
        student = User.objects.get(phone='0999999999')
        profile = student.profile
        interests = ProfileInterest.objects.filter(profile=profile).select_related('interest')
        
        if interests:
            for pi in interests:
                print(f"   {pi.interest.name}: {pi.intensity}/5")
        else:
            print("   No interests found")
    except User.DoesNotExist:
        print("   Test user not found")
    except Profile.DoesNotExist:
        print("   Profile not found")

if __name__ == '__main__':
    test_recommendations()
    show_user_interests()
    show_course_type_tags() 