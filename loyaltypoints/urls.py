from django.urls import path
from .views import LoyaltyPointDetailView, LoyaltyPointToEwalletView

urlpatterns = [
    path('me/', LoyaltyPointDetailView.as_view(), name='loyaltypoint-detail'),
    path('transform/', LoyaltyPointToEwalletView.as_view(), name='loyaltypoint-transform'),
] 