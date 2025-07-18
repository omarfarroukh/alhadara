from django_rq.decorators import job
from django.contrib.auth import get_user_model
from .models import LoyaltyPoint
from django.db import transaction

@job
def award_points_task(student_id, points, reason):
    User = get_user_model()
    try:
        student = User.objects.get(id=student_id)
    except User.DoesNotExist:
        return
    # Use transaction.atomic as a context manager (correct Django usage)
    with transaction.atomic():
        loyalty, _ = LoyaltyPoint.objects.get_or_create(student=student)  # type: ignore
        loyalty.points += points
        loyalty.save() 