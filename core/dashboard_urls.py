from django.urls import path
from .dashboard_views import (
    DashboardOverviewView,
    EnrollmentMetricsView,
    ComplaintsMetricsView,
    QuizPerformanceView,
    FeedbackMetricsView,
    FinancialMetricsView,
    RealTimeStatsView,
    BroadcastUpdateView
)

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard overview
    path('overview/', DashboardOverviewView.as_view(), name='overview'),
    
    # Detailed metrics endpoints
    path('enrollments/', EnrollmentMetricsView.as_view(), name='enrollments'),
    path('complaints/', ComplaintsMetricsView.as_view(), name='complaints'),
    path('quiz-performance/', QuizPerformanceView.as_view(), name='quiz_performance'),
    path('feedback/', FeedbackMetricsView.as_view(), name='feedback'),
    path('financial/', FinancialMetricsView.as_view(), name='financial'),
    
    # Real-time data
    path('realtime-stats/', RealTimeStatsView.as_view(), name='realtime_stats'),
    
    # Admin actions
    path('broadcast-update/', BroadcastUpdateView.as_view(), name='broadcast_update'),
]