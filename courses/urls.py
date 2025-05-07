from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet, CourseTypeViewSet, CourseViewSet,
    HallViewSet, ScheduleSlotViewSet, BookingViewSet
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'course-types', CourseTypeViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'halls', HallViewSet)
router.register(r'schedule-slots', ScheduleSlotViewSet)
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
]