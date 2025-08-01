# Generated by Django 5.1.7 on 2025-06-23 12:22

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0014_alter_enrollment_unique_together'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('notes', models.TextField(blank=True, help_text='Lesson notes and content', null=True)),
                ('file', models.FileField(blank=True, help_text='Upload lesson materials (PDF, DOC, PPT, etc.)', null=True, upload_to='lessons/files/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip'])])),
                ('link', models.URLField(blank=True, help_text='External link for lesson resources', null=True)),
                ('lesson_order', models.PositiveIntegerField(default=1, help_text='Order of lesson in the course')),
                ('lesson_date', models.DateField(help_text='Date when lesson is scheduled/conducted')),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='Completed', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='courses.course')),
                ('schedule_slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='courses.scheduleslot')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_lessons', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['lesson_date', 'lesson_order'],
                'unique_together': {('course', 'lesson_order')},
            },
        ),
        migrations.CreateModel(
            name='Homework',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(help_text='Homework description and instructions')),
                ('form_link', models.URLField(blank=True, help_text='Link to Google Form, survey, or submission form', null=True)),
                ('deadline', models.DateTimeField(help_text='Homework submission deadline')),
                ('max_score', models.PositiveIntegerField(default=100, help_text='Maximum possible score')),
                ('is_mandatory', models.BooleanField(default=True, help_text='Whether homework is mandatory')),
                ('status', models.CharField(choices=[('published', 'Published'), ('closed', 'Closed')], default='published', editable=False, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homework_assignments', to='courses.course')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assigned_homework', to=settings.AUTH_USER_MODEL)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='homework_assignments', to='courses.lesson')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance', models.CharField(choices=[('present', 'Present'), ('absent', 'Absent')], max_length=20)),
                ('notes', models.TextField(blank=True, help_text='Additional notes about attendance', null=True)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='courses.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(help_text='Teacher who recorded the attendance', on_delete=django.db.models.deletion.CASCADE, related_name='recorded_attendance', to=settings.AUTH_USER_MODEL)),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='courses.lesson')),
            ],
            options={
                'ordering': ['-recorded_at'],
                'unique_together': {('student', 'lesson')},
            },
        ),
    ]
