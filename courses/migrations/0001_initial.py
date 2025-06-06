# Generated by Django 5.1.7 on 2025-05-12 14:34

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Hall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('capacity', models.IntegerField()),
                ('location', models.CharField(max_length=255)),
                ('hourly_rate', models.DecimalField(decimal_places=2, max_digits=8)),
            ],
        ),
        migrations.CreateModel(
            name='CourseType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('category', models.CharField(choices=[('core', 'Core'), ('elective', 'Elective'), ('workshop', 'Workshop')], max_length=10)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_types', to='courses.department')),
            ],
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('duration', models.IntegerField(help_text='Duration in hours')),
                ('max_students', models.IntegerField()),
                ('certification_eligible', models.BooleanField(default=False)),
                ('teacher', models.ForeignKey(blank=True, limit_choices_to={'user_type': 'teacher'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='taught_courses', to=settings.AUTH_USER_MODEL)),
                ('course_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='courses.coursetype')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='courses.department')),
            ],
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('course', 'Course'), ('tutoring', 'Tutoring'), ('meeting', 'Meeting'), ('event', 'Event'), ('other', 'Other')], max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('cancelled', 'Cancelled')], default='pending', max_length=10)),
                ('start_datetime', models.DateTimeField()),
                ('end_datetime', models.DateTimeField()),
                ('guest_name', models.CharField(blank=True, max_length=255, null=True)),
                ('guest_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('guest_phone', models.CharField(blank=True, max_length=20, null=True)),
                ('guest_organization', models.CharField(blank=True, max_length=255, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings_requested', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(blank=True, limit_choices_to={'user_type': 'student'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings_as_student', to=settings.AUTH_USER_MODEL)),
                ('tutor', models.ForeignKey(blank=True, limit_choices_to={'user_type': 'teacher'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings_as_tutor', to=settings.AUTH_USER_MODEL)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='courses.hall')),
            ],
            options={
                'ordering': ['-start_datetime'],
                'constraints': [models.CheckConstraint(condition=models.Q(('start_datetime__lt', models.F('end_datetime'))), name='booking_start_before_end')],
            },
        ),
        migrations.CreateModel(
            name='ScheduleSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('days_of_week', models.JSONField(default=list)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('recurring', models.BooleanField(default=True)),
                ('valid_from', models.DateField()),
                ('valid_until', models.DateField(blank=True, null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedule_slots', to='courses.course')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedule_slots', to='courses.hall')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('hall', 'days_of_week', 'start_time'), name='unique_hall_schedule_per_day_time')],
            },
        ),
    ]
