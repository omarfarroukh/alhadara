# Generated by Django 5.1.7 on 2025-05-15 14:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_alter_department_description'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='department',
            options={'ordering': ['name']},
        ),
    ]
