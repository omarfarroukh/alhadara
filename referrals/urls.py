from django.urls import path
from .views import MyReferralCodeView, UseReferralCodeView, MyReferralUsagesView

urlpatterns = [
    path('my-code/', MyReferralCodeView.as_view(), name='my-referral-code'),
    path('use/', UseReferralCodeView.as_view(), name='use-referral-code'),
    path('my-usages/', MyReferralUsagesView.as_view(), name='my-referral-usages'),
] 