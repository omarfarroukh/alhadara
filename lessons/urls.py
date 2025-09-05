from rest_framework.routers import DefaultRouter
from .views import LessonViewSet, HomeworkViewSet, AttendanceViewSet, PrivateLessonRequestViewSet, ScheduleSlotNewsViewSet
from django.urls import path

router = DefaultRouter()
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'homework', HomeworkViewSet, basename='homework')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'private-lesson-requests', PrivateLessonRequestViewSet, basename='private-lesson-request')
router.register(r'newsfeed', ScheduleSlotNewsViewSet, basename='lessons-newsfeed'),

urlpatterns = router.urls 
