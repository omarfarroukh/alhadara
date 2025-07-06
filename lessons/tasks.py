from django_rq import job
from .models import Homework, ScheduleSlotNews
import logging

logger = logging.getLogger(__name__)
@job('default')
def create_homework_news_task(homework_id):
    try:
        homework = Homework.objects.select_related('lesson__schedule_slot').get(id=homework_id)
        ScheduleSlotNews.objects.create(
            schedule_slot=homework.lesson.schedule_slot,
            author=homework.teacher,
            type='homework',
            title=homework.title,
            content=homework.description,
            related_homework=homework,
        )
    except Homework.DoesNotExist:
        pass 


@job('default')
def create_quiz_news_task(quiz_id):
    import logging
    logger = logging.getLogger(__name__)
    from quiz.models import Quiz
    print(f"[TASK] starting create_quiz_news_task({quiz_id})")   # <‑‑ 1
    from lessons.models import ScheduleSlotNews


    try:
        quiz = Quiz.objects.select_related('schedule_slot', 'schedule_slot__teacher').get(pk=quiz_id)
        logger.info("⏳ Creating news for quiz %s", quiz_id)

        author = quiz.schedule_slot.teacher  # ✅ always use this

        news = ScheduleSlotNews.objects.create(
            schedule_slot = quiz.schedule_slot,
            author        = author,
            type          = 'quiz',
            title         = quiz.title,
            content       = getattr(quiz, 'description', ''),
            related_quiz  = quiz,
        )

        logger.info("✅ News item %s created for quiz %s", news.pk, quiz_id)
        print(f"[TASK] created news id {news.pk} for quiz {quiz_id}")   # <‑‑ 2


    except Exception:
        logger.exception("❌ Failed to create news for quiz %s", quiz_id)
        raise
