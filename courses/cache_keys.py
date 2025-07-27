from django.core.cache import cache

COURSES_LIST_KEY = "courses:list:{lang}"
COURSES_LIST_TIMEOUT = 60        # seconds – tune later

def courses_list_key(lang):
    return COURSES_LIST_KEY.format(lang=lang or "en")