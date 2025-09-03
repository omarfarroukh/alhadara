from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import (
    JobStatusView, PasswordResetViewSet, ProfileImageViewSet, SecurityQuestionViewSet, SecurityAnswerViewSet, InterestViewSet, TeacherViewSet,UserProfileView,
    ProfileViewSet, EWalletViewSet, DepositMethodViewSet, DepositRequestViewSet, CustomTokenObtainPairView, StudyFieldViewSet, UniversityViewSet,
    TransactionViewSet, NotificationViewSet, WithdrawalRequestViewSet, get_captcha, start_verification, verify_captcha, verify_pin
)

router = DefaultRouter()
router.register(r'security-questions', SecurityQuestionViewSet)
router.register(r'security-answers', SecurityAnswerViewSet, basename='security-answer')
router.register(r'interests', InterestViewSet)
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'profile-images', ProfileImageViewSet, basename='profileimage')
router.register(r'wallets', EWalletViewSet, basename='wallet')
router.register(r'deposit-methods', DepositMethodViewSet)
router.register(r'deposit-requests', DepositRequestViewSet, basename='deposit-request')
router.register(r'withdrawals', WithdrawalRequestViewSet, basename='withdrawal')
router.register(r'reset-password', PasswordResetViewSet, basename='password-reset')
router.register(r'universities', UniversityViewSet)
router.register(r'studyfields', StudyFieldViewSet)
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'teachers', TeacherViewSet, basename='teacher')


urlpatterns = [
    # JWT Authentication endpoints
    path('auth/jwt/create/', CustomTokenObtainPairView.as_view(), name='jwt-create'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt-refresh'),
    path('auth/jwt/verify/', TokenVerifyView.as_view(), name='jwt-verify'),
    path('profile/me/', UserProfileView.as_view(), name='user-profile'),
    path('auth/verify/start/', start_verification, name='start-verification'),
    path('auth/verify/submit/', verify_pin, name='verify-pin'),
    path('api/captcha/',        get_captcha,   name='get-captcha'),
    path('api/captcha/verify/', verify_captcha, name='verify-captcha'),
    # Router URLs
    path('', include(router.urls)),
    path("jobs/<uuid:job_id>/", JobStatusView.as_view())
]