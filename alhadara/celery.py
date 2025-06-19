from eventlet import monkey_patch
monkey_patch()

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')

app = Celery('alhadara')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()