from datetime import timedelta
import django_rq
from django_rq.decorators import job
from django.utils import timezone
from rq import get_current_job
import logging
from django.db import transaction
from courses.models import Enrollment, ScheduleSlot
from lessons.models import Attendance, HomeworkGrade
from loyaltypoints.tasks import award_points_task
from quiz.models import QuizAttempt   # add this
from django.db.models import Avg
from decimal import Decimal


logger = logging.getLogger(__name__)
@transaction.atomic
def apply_course_discount(discount_id):
    try:
        from .models import CourseDiscount

        # lock this discount row (and implicitly the course row via FK)
        discount = CourseDiscount.objects.select_related('course').select_for_update().get(
            id=discount_id,
            status='active'
        )

        now = timezone.now()
        if now < discount.start_date:
            logger.warning("Discount %s – not yet time", discount_id)
            return "Discount not yet due"

        # ---- guard: another active one? ----
        if CourseDiscount.objects.filter(
            course_id=discount.course_id,
            status='active'
        ).exclude(pk=discount.pk).exists():
            logger.error(
                "Course %s already has an active discount – cancelling this one",
                discount.course_id
            )
            discount.status = 'cancelled'
            discount.save(update_fields=['status'])
            return "Cancelled – duplicate active discount"

        # ---- safe to activate ----
        discount.apply_discount()
        logger.info(
            "Activated discount %s for course %s (%.1f%% off)",
            discount.id,
            discount.course.title,
            discount.discount_percentage
        )
        return f"Discount applied for {discount.course.title}"

    except CourseDiscount.DoesNotExist:
        logger.warning("Discount %s not found or not active", discount_id)
    except Exception as e:
        logger.exception("Error applying discount %s: %s", discount_id, e)
        raise
    
@transaction.atomic                # <-- wrap the whole task
def remove_course_discount(discount_id):
    """RQ task to remove a course discount"""
    try:
        from .models import CourseDiscount
        
        discount = CourseDiscount.objects.select_for_update().get(
            id=discount_id,
            status='active'
        )
        
        discount.remove_discount()
        logger.info(f"Removed discount for course: {discount.course.title}")
        return f"Discount removed successfully for {discount.course.title}"
        
    except Exception as e:
        logger.error(f"Error removing discount {discount_id}: {str(e)}")
        raise

def cancel_scheduled_job(job_id):
    """Cancel a scheduled RQ job"""
    try:
        scheduler = django_rq.get_scheduler('default')
        scheduler.cancel(job_id)
        logger.info(f"Cancelled job: {job_id}")
    except Exception as e:
        logger.warning(f"Could not cancel job {job_id}: {str(e)}")
        
        
        
@job('default')
def award_points_for_top_performers():
    """
    A daily task that finds schedule slots that ended yesterday,
    calculates the top 3 performers, and awards them loyalty points.
    """
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Find all schedule slots that officially ended yesterday
    completed_slots = ScheduleSlot.objects.filter(valid_until=yesterday).select_related('course')

    for slot in completed_slots:
        enrollments = Enrollment.objects.filter(
            schedule_slot=slot, 
            status='completed', 
            is_guest=False # Only award points to registered students
        ).select_related('student')
        
        student_scores = []
        for enr in enrollments:
            # --- Attendance Score ---
            total_lessons = slot.lessons_in_lessons_app.filter(status='completed').count()
            present_count = Attendance.objects.filter(enrollment=enr, attendance='present').count()
            attendance_pct = Decimal(present_count / total_lessons * 100) if total_lessons > 0 else Decimal('0.0')
            
            # --- Homework Score ---
            avg_hw_grade = HomeworkGrade.objects.filter(enrollment=enr).aggregate(avg=Avg('grade'))['avg']
            # Ensure grade is a Decimal and handle None case
            avg_hw_grade = Decimal(avg_hw_grade) if avg_hw_grade is not None else Decimal('0.0')

            # --- Quiz Score ---
            avg_quiz_score = QuizAttempt.objects.filter(
                user=enr.student, 
                quiz__schedule_slot=slot, 
                status='completed'
            ).aggregate(avg=Avg('score'))['avg']
            # Ensure score is a Decimal and handle None case
            avg_quiz_score = Decimal(avg_quiz_score) if avg_quiz_score is not None else Decimal('0.0')

            # --- Weighted Overall Grade (using Decimals for precision) ---
            overall_grade = (attendance_pct * Decimal('0.3')) + (avg_hw_grade * Decimal('0.4')) + (avg_quiz_score * Decimal('0.3'))
            
            student_scores.append({'student_id': enr.student.id, 'score': overall_grade})

        # Sort by score to find the top performers
        top_performers = sorted(student_scores, key=lambda x: x['score'], reverse=True)

        # Award points to the top 3
        points_map = {0: 10, 1: 7, 2: 5} # Rank -> Points
        for i, perf in enumerate(top_performers[:3]):
            points = points_map[i]
            reason = f"Top performer award for the course '{slot.course.title}'"
            award_points_task.delay(perf['student_id'], points, reason)

    return f"Checked for top performers in {completed_slots.count()} completed slots."