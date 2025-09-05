# loyaltypoints/tasks.py
from django_rq.decorators import job
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal

from courses.models import Booking, Enrollment
from .models import LoyaltyPoint, LoyaltyPointLog
from core.models import Transaction
from core.tasks import send_notification_task
from django.db.models import Q

User = get_user_model()

@job('default')
def award_points_task(student_id, points_to_award, reason_message):
    """
    Awards loyalty points by creating a log entry and updating the total.
    This is now a generic task called when points are confirmed to be awarded.
    """
    try:
        student = User.objects.get(id=student_id, user_type='student')
    except User.DoesNotExist:
        return f"User {student_id} not found or is not a student."

    if points_to_award <= 0: return "Points must be positive."

    with transaction.atomic():
        account, _ = LoyaltyPoint.objects.get_or_create(student=student)
        LoyaltyPointLog.objects.create(loyalty_account=account, points=points_to_award, reason=reason_message)
        account.points += points_to_award
        account.save()

    send_notification_task.delay(
        recipient_id=student_id, notification_type='points_earned',
        title=f"🎉 You've Earned {points_to_award} Points!",
        message=f"Reason: {reason_message}",
        data={'points_awarded': points_to_award, 'new_total': account.points}
    )
    return f"Awarded {points_to_award} points to student {student_id}."

@job('default')
def award_points_for_cleared_transactions_task():
    """
    A daily scheduled task to find transactions past their cancellation window
    and award loyalty points for them, using a two-step query.
    """
    today = timezone.now().date()
    
    # --- 1. Process Enrollment Transactions ---

    # Step 1.1: Find all enrollment IDs that are past their cancellation window.
    cleared_enrollment_ids = list(Enrollment.objects.filter(
        schedule_slot__valid_from__lt=today
    ).values_list('id', flat=True))

    awarded_count = 0
    processed_enrollment_txns = 0

    if cleared_enrollment_ids:
        # Step 1.2: Build a dynamic query to find all matching transactions.
        q_objects = Q()
        for enrollment_id in cleared_enrollment_ids:
            q_objects |= Q(reference_id__startswith=f"ENR-{enrollment_id}-")

        enrollment_transactions = Transaction.objects.filter(
            q_objects,
            loyalty_points_awarded=False,
            transaction_type='course_payment',
            status='completed'
        ).select_related('receiver').distinct()
        
        processed_enrollment_txns = enrollment_transactions.count()

        for txn in enrollment_transactions:
            student = txn.receiver
            if student and student.user_type == 'student':
                points = int(txn.amount * Decimal('0.025'))
                if points > 0:
                    reason = f"Payment for course enrollment"
                    award_points_task.delay(student.id, points, reason)
                    awarded_count += 1
            txn.loyalty_points_awarded = True
            txn.save(update_fields=['loyalty_points_awarded'])

    # --- 2. Process Booking Transactions ---

    # Step 2.1: Find all booking IDs that are past their cancellation window.
    cleared_booking_ids = list(Booking.objects.filter(
        date__lt=today
    ).values_list('id', flat=True))
    
    processed_booking_txns = 0

    if cleared_booking_ids:
        # Step 2.2: Build a dynamic query to find all matching booking transactions.
        q_objects = Q()
        for booking_id in cleared_booking_ids:
            # Match both cash and e-wallet booking patterns
            q_objects |= Q(reference_id__startswith=f"BK-EW-{booking_id}-")
            q_objects |= Q(reference_id__startswith=f"BK-CASH-{booking_id}-")

        booking_transactions = Transaction.objects.filter(
            q_objects,
            loyalty_points_awarded=False,
            transaction_type='booking_payment',
            status='completed'
        ).select_related('sender').distinct()
        
        processed_booking_txns = booking_transactions.count()

        for txn in booking_transactions:
            student = txn.sender
            # Ensure we don't award points to the generic 'guest' user
            if student and student.user_type == 'student' and student.phone != 'guest':
                points = int(txn.amount * Decimal('0.025'))
                if points > 0:
                    reason = f"Payment for hall booking"
                    award_points_task.delay(student.id, points, reason)
                    awarded_count += 1
            txn.loyalty_points_awarded = True
            txn.save(update_fields=['loyalty_points_awarded'])
        
    total_processed = processed_enrollment_txns + processed_booking_txns
    return f"Processed {total_processed} transactions. Awarded points for {awarded_count} of them."