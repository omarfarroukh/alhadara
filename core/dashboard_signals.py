from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def broadcast_dashboard_update(event_type, model_name, instance_id=None):
    """
    Broadcast dashboard update to all connected supervisors
    """
    try:
        channel_layer = get_channel_layer()
        
        update_data = {
            "event_type": event_type,
            "model": model_name,
            "instance_id": instance_id,
            "timestamp": timezone.now().isoformat()
        }
        
        # Send to supervisor dashboard group
        async_to_sync(channel_layer.group_send)(
            "supervisor_dashboard",
            {
                "type": "dashboard_update_broadcast",
                "data": update_data
            }
        )
        
        logger.info(f"Dashboard update broadcasted: {event_type} {model_name}")
        
    except Exception as e:
        logger.error(f"Failed to broadcast dashboard update: {e}")

# User-related signals
@receiver(post_save, sender='core.User')
def user_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when user is created or updated"""
    event_type = "user_created" if created else "user_updated"
    broadcast_dashboard_update(event_type, "User", instance.id)

# Enrollment signals
@receiver(post_save, sender='courses.Enrollment')
def enrollment_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when enrollment is created or updated"""
    event_type = "enrollment_created" if created else "enrollment_updated"
    
    # Check if this is a payment update
    if not created and hasattr(instance, '_previous_amount_paid'):
        if instance.amount_paid != instance._previous_amount_paid:
            event_type = "payment_received"
    
    broadcast_dashboard_update(event_type, "Enrollment", instance.id)

@receiver(post_delete, sender='courses.Enrollment')
def enrollment_deleted(sender, instance, **kwargs):
    """Trigger dashboard update when enrollment is deleted"""
    broadcast_dashboard_update("enrollment_deleted", "Enrollment", instance.id)

# Quiz attempt signals
@receiver(post_save, sender='quiz.QuizAttempt')
def quiz_attempt_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when quiz attempt is created or updated"""
    event_type = "quiz_attempt_created" if created else "quiz_attempt_updated"
    broadcast_dashboard_update(event_type, "QuizAttempt", instance.id)

# Complaint signals
@receiver(post_save, sender='complaints.Complaint')
def complaint_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when complaint is created or updated"""
    event_type = "complaint_created" if created else "complaint_updated"
    broadcast_dashboard_update(event_type, "Complaint", instance.id)

@receiver(post_delete, sender='complaints.Complaint')
def complaint_deleted(sender, instance, **kwargs):
    """Trigger dashboard update when complaint is deleted"""
    broadcast_dashboard_update("complaint_deleted", "Complaint", instance.id)

# Feedback signals
@receiver(post_save, sender='feedback.Feedback')
def feedback_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when feedback is created or updated"""
    event_type = "feedback_created" if created else "feedback_updated"
    broadcast_dashboard_update(event_type, "Feedback", instance.id)

# Course signals
@receiver(post_save, sender='courses.Course')
def course_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when course is created or updated"""
    event_type = "course_created" if created else "course_updated"
    broadcast_dashboard_update(event_type, "Course", instance.id)

# Schedule slot signals
@receiver(post_save, sender='courses.ScheduleSlot')
def schedule_slot_created_updated(sender, instance, created, **kwargs):
    """Trigger dashboard update when schedule slot is created or updated"""
    event_type = "schedule_slot_created" if created else "schedule_slot_updated"
    broadcast_dashboard_update(event_type, "ScheduleSlot", instance.id)

# Transaction signals
try:
    @receiver(post_save, sender='core.Transaction')
    def transaction_created_updated(sender, instance, created, **kwargs):
        """Trigger dashboard update when transaction is created or updated"""
        if instance.transaction_type == 'course_payment':
            event_type = "payment_transaction_created" if created else "payment_transaction_updated"
            broadcast_dashboard_update(event_type, "Transaction", instance.id)
except:
    logger.warning("Transaction model not found - signal not registered")
    pass

# Loyalty points signals (if available)
try:
    @receiver(post_save, sender='loyaltypoints.LoyaltyPoint')
    def loyalty_point_created_updated(sender, instance, created, **kwargs):
        """Trigger dashboard update when loyalty point is created or updated"""
        event_type = "loyalty_point_created" if created else "loyalty_point_updated"
        broadcast_dashboard_update(event_type, "LoyaltyPoint", instance.id)
except:
    # Handle case where loyaltypoints app might not be available
    logger.warning("LoyaltyPoint model not found - signal not registered")
    pass