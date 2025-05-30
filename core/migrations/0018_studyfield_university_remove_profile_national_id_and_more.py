# Generated by Django 5.1.7 on 2025-05-28 14:51

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_alter_depositrequest_screenshot_path'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudyField',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='University',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='profile',
            name='national_id',
        ),
        migrations.AddField(
            model_name='profile',
            name='academic_status',
            field=models.CharField(blank=True, choices=[('high_school', 'High School'), ('undergraduate', 'Undergraduate'), ('graduate', 'Graduate'), ('not_studying', 'Not Currently Studying')], max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='gender',
            field=models.CharField(choices=[('male', 'Male'), ('female', 'Female')], default='male', max_length=10),
        ),
        migrations.AddField(
            model_name='profile',
            name='studyfield',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='core.studyfield'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='profile',
            name='university',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='profile', to='core.university'),
            preserve_default=False,
        ),
    ]
