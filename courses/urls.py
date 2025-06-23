from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet, CourseTypeViewSet, CourseViewSet,
    HallViewSet, ScheduleSlotViewSet, BookingViewSet, WishlistViewSet,
    UnifiedSearchViewSet, EnrollmentViewSet, ActiveCourseViewSet,
    LessonViewSet, HomeworkViewSet, AttendanceViewSet 
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'course-types', CourseTypeViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'halls', HallViewSet)
router.register(r'schedule-slots', ScheduleSlotViewSet)
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'wishlists', WishlistViewSet, basename='wishlist')
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'search', UnifiedSearchViewSet, basename='unified-search')
router.register(r'active-courses', ActiveCourseViewSet, basename='active-course')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'homework', HomeworkViewSet, basename='homework')
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
]