from rest_framework.routers import DefaultRouter
from .views import LessonViewSet, HomeworkViewSet, AttendanceViewSet

router = DefaultRouter()
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'homework', HomeworkViewSet, basename='homework')
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = router.urls 