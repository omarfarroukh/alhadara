import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path  # Add your WebSocket routes here

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alhadara.settings')

# Initialize Django ASGI application early for HTTP requests
django_asgi_app = get_asgi_application()

# Define WebSocket routing (replace with your actual WebSocket consumers)
from core.consumers import NotificationConsumer  # Example consumer
from core.middleware import JWTAuthMiddleware  # Import our custom middleware

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # HTTP traffic
    "websocket": JWTAuthMiddleware(  # WebSocket traffic with JWT auth
        URLRouter(websocket_urlpatterns)
    ),
})