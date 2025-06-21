from django.core.management.base import BaseCommand
from core.models import Interest, StudyField
from courses.models import Department, CourseType, CourseTypeTag

class Command(BaseCommand):
    help = 'Seed course type tags for the recommendation system'

    def handle(self, *args, **options):
        self.stdout.write('Seeding course type tags...')
        
        # Get existing interests and study fields
        interests = {interest.name: interest for interest in Interest.objects.all()}
        study_fields = {field.name: field for field in StudyField.objects.all()}
        departments = {dept.name: dept for dept in Department.objects.all()}
        
        # Course types with their tags
        course_types_data = [
            ('Programming Languages', 'Computer Science', ['Programming', 'Computer Science'], ['Computer Science']),
            ('Web Development', 'Computer Science', ['Programming', 'Web Development', 'Design'], ['Computer Science']),
            ('Mobile Development', 'Computer Science', ['Programming', 'Mobile Development'], ['Computer Science']),
            ('Data Science', 'Computer Science', ['Data Science', 'Mathematics'], ['Computer Science', 'Mathematics']),
            ('Artificial Intelligence', 'Computer Science', ['Artificial Intelligence', 'Computer Science'], ['Computer Science']),
            ('English Language', 'Languages', ['Literature'], ['Literature']),
            ('Arabic Language', 'Languages', ['Literature'], ['Literature']),
            ('French Language', 'Languages', ['Literature'], ['Literature']),
            ('German Language', 'Languages', ['Literature'], ['Literature']),
            ('Spanish Language', 'Languages', ['Literature'], ['Literature']),
            ('Business Management', 'Business', ['Business', 'Management'], ['Business']),
            ('Marketing', 'Business', ['Marketing', 'Business'], ['Business']),
            ('Finance', 'Business', ['Business'], ['Business']),
            ('Entrepreneurship', 'Business', ['Business', 'Management'], ['Business']),
            ('Project Management', 'Business', ['Management', 'Business'], ['Business']),
        ]
        
        for name, dept_name, interest_names, study_field_names in course_types_data:
            try:
                course_type = CourseType.objects.get(name=name)
                self.stdout.write(f'Processing course type: {name}')
                
                # Add interest tags
                for interest_name in interest_names:
                    if interest_name in interests:
                        course_type.add_interest_tag(interests[interest_name])
                        self.stdout.write(f'  ✓ Added interest tag: {interest_name}')
                    else:
                        self.stdout.write(f'  ⚠ Interest not found: {interest_name}')
                
                # Add study field tags
                for study_field_name in study_field_names:
                    if study_field_name in study_fields:
                        course_type.add_study_field_tag(study_fields[study_field_name])
                        self.stdout.write(f'  ✓ Added study field tag: {study_field_name}')
                    else:
                        self.stdout.write(f'  ⚠ Study field not found: {study_field_name}')
                        
            except CourseType.DoesNotExist:
                self.stdout.write(f'  ❌ Course type not found: {name}')
        
        self.stdout.write(self.style.SUCCESS('Course type tags seeding completed!'))
        
        # Show summary
        self.stdout.write('\n📊 Summary:')
        for course_type in CourseType.objects.all():
            tags = course_type.get_tags()
            if tags['interests'] or tags['study_fields']:
                self.stdout.write(f'\n📖 {course_type.name}:')
                if tags['interests']:
                    self.stdout.write(f'   Interests: {", ".join(tags["interests"])}')
                if tags['study_fields']:
                    self.stdout.write(f'   Study Fields: {", ".join(tags["study_fields"])}') 