from django.db.models.signals import post_save,pre_save
from django.dispatch import receiver
from .models import Homework
from django.db import transaction
from quiz.models import Quiz
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Homework)
def create_homework_news_async(sender, instance, created, **kwargs):
    if created:
        logger.info(f"Homework signal triggered for homework {instance.id}")
        from lessons.tasks import create_homework_news_task
        create_homework_news_task.delay(instance.id)

@receiver(pre_save, sender=Quiz)
def cache_old_is_active(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = Quiz.objects.only('is_active').get(pk=instance.pk)
            instance._old_is_active = old.is_active
        except Quiz.DoesNotExist:
            instance._old_is_active = None
    else:
        # New instance, no old value
        instance._old_is_active = None

@receiver(post_save, sender=Quiz)
def create_quiz_news_async(sender, instance, created, **kwargs):
    from .tasks import create_quiz_news_task
    old_is_active = getattr(instance, '_old_is_active', None)

    # Check if quiz became active (new or updated)
    if instance.is_active:
        if created:
            # New active quiz
            transaction.on_commit(lambda: create_quiz_news_task.delay(instance.pk))
        else:
            # Updated quiz — only if previously inactive or unknown
            if old_is_active is False or old_is_active is None:
                transaction.on_commit(lambda: create_quiz_news_task.delay(instance.pk))
