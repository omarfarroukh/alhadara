from rest_framework.routers import DefaultRouter
from .views import DashboardViewSet

router = DefaultRouter()
# The 'basename' is required because there's no queryset on the viewset
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = router.urls