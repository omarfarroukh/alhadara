import os, django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path

# Ensure settings are configured *before* any model import
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')
django.setup()          # <── important

# Now it is safe to import consumers that touch models
from lessons.consumers import NewsFeedConsumer
from core.consumers import NotificationConsumer
from core.middleware import JWTAuthMiddleware

websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
    re_path(r'^ws/news/(?P<slot_id>\d+)/$', NewsFeedConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})