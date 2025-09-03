import django_rq
from django.utils import timezone
from rq import get_current_job
import logging
from django.db import transaction   # add this

logger = logging.getLogger(__name__)
@transaction.atomic                # <-- wrap the whole task
def apply_course_discount(discount_id):
    """RQ task to apply a course discount"""
    try:
        from .models import CourseDiscount
        
        discount = CourseDiscount.objects.select_for_update().get(
            id=discount_id,
            status='active'
        )
        
        # Check if it's time to apply the discount
        now = timezone.now()
        if now >= discount.start_date:
            discount.apply_discount()
            logger.info(f"Applied discount for course: {discount.course.title}")
            return f"Discount applied successfully for {discount.course.title}"
        else:
            logger.warning(f"Attempted to apply discount too early for course: {discount.course.title}")
            return "Discount not yet due to be applied"
            
    except Exception as e:
        logger.error(f"Error applying discount {discount_id}: {str(e)}")
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
