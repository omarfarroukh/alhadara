#!/usr/bin/env python
"""
Script to add schedule slots to courses for testing schedule validation
Run this after seeding courses to ensure recommendations work
"""

import os
import django
from datetime import date, timedelta, time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()

from courses.models import Course, ScheduleSlot, Hall
from django.contrib.auth import get_user_model

User = get_user_model()

def add_schedule_slots():
    """Add schedule slots to courses for testing"""
    print("📅 Adding schedule slots to courses...")
    
    # Get or create a hall
    hall, created = Hall.objects.get_or_create(
        name='Main Hall',
        defaults={
            'capacity': 30,
            'location': 'First Floor',
            'hourly_rate': 50.00
        }
    )
    if created:
        print(f"✅ Created hall: {hall.name}")
    
    # Get or create a teacher
    teacher, created = User.objects.get_or_create(
        phone='0988888888',
        defaults={
            'first_name': 'John',
            'middle_name': 'Smith',
            'last_name': 'Doe',
            'password': 'Teacher@123',
            'user_type': 'teacher'
        }
    )
    if created:
        print(f"✅ Created teacher: {teacher.get_full_name()}")
    
    # Get all courses
    courses = Course.objects.all()
    
    # Create schedule slots for each course
    for course in courses:
        # Create multiple schedule slots with different start dates
        start_dates = [
            date.today() + timedelta(days=7),   # Next week
            date.today() + timedelta(days=14),  # 2 weeks from now
            date.today() + timedelta(days=30),  # 1 month from now
            date.today() + timedelta(days=60),  # 2 months from now
        ]
        
        for i, start_date in enumerate(start_dates):
            # Create schedule slot
            slot, created = ScheduleSlot.objects.get_or_create(
                course=course,
                hall=hall,
                teacher=teacher,
                days_of_week=['mon', 'wed', 'fri'],  # Monday, Wednesday, Friday
                start_time=time(9, 0),  # 9:00 AM
                end_time=time(11, 0),   # 11:00 AM
                recurring=True,
                valid_from=start_date,
                valid_until=start_date + timedelta(days=30)  # 1 month duration
            )
            
            if created:
                print(f"✅ Added schedule slot for {course.title} starting {start_date}")
    
    print("\n✅ Schedule slots added successfully!")
    
    # Show summary
    print("\n📊 Schedule Summary:")
    for course in courses:
        slot_count = course.schedule_slots.count()
        upcoming_slots = course.schedule_slots.filter(
            valid_from__gte=date.today(),
            valid_from__lte=date.today() + timedelta(days=90)
        ).count()
        print(f"   {course.title}: {slot_count} total slots, {upcoming_slots} upcoming")

if __name__ == '__main__':
    add_schedule_slots() 