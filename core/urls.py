from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import (
    PasswordResetViewSet, SecurityQuestionViewSet, SecurityAnswerViewSet, InterestViewSet,
    ProfileViewSet, EWalletViewSet, DepositMethodViewSet, DepositRequestViewSet, CustomTokenObtainPairView, StudyFieldViewSet, UniversityViewSet
)

router = DefaultRouter()
router.register(r'security-questions', SecurityQuestionViewSet)
router.register(r'security-answers', SecurityAnswerViewSet, basename='security-answer')
router.register(r'interests', InterestViewSet)
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'wallets', EWalletViewSet, basename='wallet')
router.register(r'deposit-methods', DepositMethodViewSet)
router.register(r'deposit-requests', DepositRequestViewSet, basename='deposit-request')
router.register(r'reset-password', PasswordResetViewSet, basename='password-reset')
router.register(r'universities', UniversityViewSet)
router.register(r'studyfields', StudyFieldViewSet)

urlpatterns = [
    # JWT Authentication endpoints
    path('auth/jwt/create/', CustomTokenObtainPairView.as_view(), name='jwt-create'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('auth/jwt/verify/', TokenVerifyView.as_view(), name='jwt-verify'),
    
    # Router URLs
    path('', include(router.urls)),
]