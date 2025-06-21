#!/usr/bin/env python
"""
Quick script to seed some basic course type tags for testing
Run this after your main seed_data command
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()

from core.models import Interest, StudyField
from courses.models import CourseType, CourseTypeTag

def quick_seed_tags():
    """Quickly seed some basic tags for testing"""
    print("🏷️  Quick seeding course type tags...")
    
    # Get or create basic interests and study fields
    interests = {}
    for name in ['Programming', 'Web Development', 'Mathematics', 'Design', 'Business']:
        interest, _ = Interest.objects.get_or_create(name=name, defaults={'category': 'professional'})
        interests[name] = interest
    
    study_fields = {}
    for name in ['Computer Science', 'Engineering', 'Mathematics', 'Business']:
        study_field, _ = StudyField.objects.get_or_create(name=name)
        study_fields[name] = study_field
    
    # Basic course type tags
    tags_data = [
        ('Programming Languages', ['Programming'], ['Computer Science']),
        ('Web Development', ['Programming', 'Web Development', 'Design'], ['Computer Science']),
        ('Mobile Development', ['Programming'], ['Computer Science']),
        ('Data Science', ['Programming', 'Mathematics'], ['Computer Science', 'Mathematics']),
        ('Business Management', ['Business'], ['Business']),
        ('Marketing', ['Business'], ['Business']),
    ]
    
    for course_type_name, interest_names, study_field_names in tags_data:
        try:
            course_type = CourseType.objects.get(name=course_type_name)
            print(f"📖 Processing: {course_type_name}")
            
            # Add interest tags
            for interest_name in interest_names:
                if interest_name in interests:
                    CourseTypeTag.objects.get_or_create(
                        course_type=course_type,
                        interest=interests[interest_name],
                        study_field=None
                    )
                    print(f"  ✓ Added interest: {interest_name}")
            
            # Add study field tags
            for study_field_name in study_field_names:
                if study_field_name in study_fields:
                    CourseTypeTag.objects.get_or_create(
                        course_type=course_type,
                        interest=None,
                        study_field=study_fields[study_field_name]
                    )
                    print(f"  ✓ Added study field: {study_field_name}")
                    
        except CourseType.DoesNotExist:
            print(f"  ❌ Course type not found: {course_type_name}")
    
    print("\n✅ Quick tag seeding completed!")
    
    # Show summary
    print("\n📊 Current tags:")
    for course_type in CourseType.objects.all():
        tags = course_type.get_tags()
        if tags['interests'] or tags['study_fields']:
            print(f"\n📖 {course_type.name}:")
            if tags['interests']:
                print(f"   Interests: {', '.join(tags['interests'])}")
            if tags['study_fields']:
                print(f"   Study Fields: {', '.join(tags['study_fields'])}")

if __name__ == '__main__':
    quick_seed_tags() 