from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Course, Wishlist, ScheduleSlot
from .cache_keys import COURSES_LIST_KEY

def _bust_courses_cache(sender, **kwargs):
    from django.core.cache import cache
    # Flush every language variant (cheap with Redis)
    cache.delete_pattern(COURSES_LIST_KEY.replace('{lang}', '*'))

for model in (Course, Wishlist, ScheduleSlot):
    post_save.connect(_bust_courses_cache, sender=model)
    post_delete.connect(_bust_courses_cache, sender=model)