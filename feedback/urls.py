from django.urls import path
from .views import FeedbackCreateView, FeedbackListByScheduleSlotView

urlpatterns = [
    path('submit/', FeedbackCreateView.as_view(), name='feedback-submit'),
    path('admin/by-scheduleslot/', FeedbackListByScheduleSlotView.as_view(), name='feedback-by-scheduleslot'),
] 