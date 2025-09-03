from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseDiscountViewSet, CourseImageViewSet, CourseTypeIconViewSet, DepartmentIconViewSet, DepartmentViewSet, CourseTypeViewSet, CourseViewSet, HallServiceViewSet,
    HallViewSet, ScheduleSlotViewSet, BookingViewSet, WishlistViewSet,
    UnifiedSearchViewSet, EnrollmentViewSet
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
router.register(r'hall-services', HallServiceViewSet, basename='hallservice')
router.register(r'course-type-icon', CourseTypeIconViewSet, basename='course-type-icon')
router.register(r'department-icon', DepartmentIconViewSet, basename='departmente-icon')
router.register(r'course-images', CourseImageViewSet, basename='course--images')
router.register(r'course-discounts', CourseDiscountViewSet)

urlpatterns = [
    path('', include(router.urls)),
]