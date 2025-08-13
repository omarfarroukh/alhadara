from django.core.management.base import BaseCommand
from entranceexam.models import Language, LanguageLevel


class Command(BaseCommand):
    help = 'Initialize language and language level data'

    def handle(self, *args, **options):
        self.stdout.write('Setting up language data...')
        
        # Create languages
        languages_data = [
            {'name': 'english', 'is_active': True},
            {'name': 'german', 'is_active': True},
            {'name': 'french', 'is_active': True},
            {'name': 'spanish', 'is_active': True},
        ]
        
        for lang_data in languages_data:
            language, created = Language.objects.get_or_create(
                name=lang_data['name'],
                defaults={'is_active': lang_data['is_active']}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created language: {language.get_name_display()}')
                )
            else:
                self.stdout.write(f'Language already exists: {language.get_name_display()}')
        
        # Create language levels
        levels_data = [
            {'level': 'a1', 'min_score': 0, 'max_score': 29},
            {'level': 'a2', 'min_score': 30, 'max_score': 49},
            {'level': 'b1', 'min_score': 50, 'max_score': 69},
            {'level': 'b2', 'min_score': 70, 'max_score': 84},
            {'level': 'c1', 'min_score': 85, 'max_score': 94},
            {'level': 'c2', 'min_score': 95, 'max_score': 100},
        ]
        
        for level_data in levels_data:
            level, created = LanguageLevel.objects.get_or_create(
                level=level_data['level'],
                defaults={
                    'min_score': level_data['min_score'],
                    'max_score': level_data['max_score']
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created level: {level.get_level_display()} ({level.min_score}-{level.max_score}%)')
                )
            else:
                self.stdout.write(f'Level already exists: {level.get_level_display()}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully initialized language data!')
        ) 