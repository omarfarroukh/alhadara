from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SecurityQuestionViewSet, SecurityAnswerViewSet, InterestViewSet,
    ProfileViewSet, EWalletViewSet, DepositMethodViewSet, DepositRequestViewSet
)

router = DefaultRouter()
router.register(r'security-questions', SecurityQuestionViewSet)
router.register(r'security-answers', SecurityAnswerViewSet, basename='security-answer')
router.register(r'interests', InterestViewSet)
router.register(r'profiles', ProfileViewSet, basename='profile')
router.register(r'wallets', EWalletViewSet, basename='wallet')
router.register(r'deposit-methods', DepositMethodViewSet)
router.register(r'deposit-requests', DepositRequestViewSet, basename='deposit-request')

urlpatterns = [
    path('', include(router.urls)),
]