# Generated by Django 5.1.7 on 2025-05-15 15:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_alter_department_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='coursetype',
            name='category',
        ),
        migrations.AddField(
            model_name='course',
            name='category',
            field=models.CharField(choices=[('course', 'course'), ('workshop', 'Workshop')], default='course', max_length=10),
            preserve_default=False,
        ),
    ]
