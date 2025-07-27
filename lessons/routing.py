from django.urls import re_path
from .consumers import NewsFeedConsumer

websocket_urlpatterns = [
    re_path(r'ws/news/(?P<slot_id>\d+)/$', NewsFeedConsumer.as_asgi()),
]