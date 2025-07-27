from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg, Q, Sum, F
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

User = get_user_model()

class SupervisorDashboardPermission:
    """Custom permission for supervisor dashboard access"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.user_type in ['admin', 'reception']
        )

class DashboardOverviewView(APIView):
    """Get dashboard overview metrics"""
    permission_classes = [IsAuthenticated]
    
    def has_permission(self, request, view):
        return SupervisorDashboardPermission().has_permission(request, view)
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from courses.models import Course, Enrollment, ScheduleSlot
            from quiz.models import Quiz, QuizAttempt
            from complaints.models import Complaint
            from feedback.models import Feedback
            
            now = timezone.now()
            today = now.date()
            week_ago = today - timedelta(days=7)
            
                         # Financial metrics for overview
             total_revenue = Enrollment.objects.filter(
                 payment_status__in=['paid', 'partial']
             ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
             
             todays_revenue = Enrollment.objects.filter(
                 updated_at__date=today,
                 payment_status__in=['paid', 'partial']
             ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
             
             outstanding_revenue = Enrollment.objects.filter(
                 status='active',
                 payment_status='partial'
             ).aggregate(
                 total=Sum(F('course__price') - F('amount_paid'))
             )['total'] or Decimal('0.00')
             
             # Get comprehensive metrics
             data = {
                 "overview": {
                     "total_users": User.objects.count(),
                     "active_students": User.objects.filter(
                         user_type='student', 
                         is_active=True,
                         last_login__gte=week_ago
                     ).count(),
                     "total_courses": Course.objects.count(),
                     "active_courses": Course.objects.filter(is_active=True).count(),
                     "total_enrollments": Enrollment.objects.count(),
                     "active_enrollments": Enrollment.objects.filter(status='active').count(),
                     "total_revenue": float(total_revenue),
                     "outstanding_revenue": float(outstanding_revenue)
                 },
                "alerts": {
                    "pending_enrollments": Enrollment.objects.filter(status='pending').count(),
                    "pending_complaints": Complaint.objects.filter(
                        status__in=['submitted', 'in_review']
                    ).count(),
                    "high_priority_complaints": Complaint.objects.filter(
                        priority='high',
                        status__in=['submitted', 'in_review']
                    ).count(),
                    "unverified_users": User.objects.filter(
                        is_verified=False,
                        user_type='student'
                    ).count(),
                },
                "today": {
                    "new_students": User.objects.filter(
                        user_type='student',
                        date_joined__date=today
                    ).count(),
                    "new_enrollments": Enrollment.objects.filter(
                        created_at__date=today
                    ).count(),
                    "classes_scheduled": ScheduleSlot.objects.filter(
                        date=today,
                        is_active=True
                    ).count(),
                    "quiz_attempts": QuizAttempt.objects.filter(
                        started_at__date=today
                    ).count(),
                                         "new_complaints": Complaint.objects.filter(
                         created_at__date=today
                     ).count(),
                     "todays_revenue": float(todays_revenue)
                 }
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch dashboard data: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EnrollmentMetricsView(APIView):
    """Get detailed enrollment metrics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from courses.models import Enrollment
            
            # Enrollment statistics
            by_status = list(Enrollment.objects.values('status').annotate(count=Count('id')))
            by_course = list(Enrollment.objects.values('course__title').annotate(count=Count('id')).order_by('-count')[:10])
            
            # Recent enrollments
            recent = Enrollment.objects.select_related('student', 'course').order_by('-created_at')[:20]
            recent_data = [{
                'student_name': f"{enrollment.student.first_name} {enrollment.student.last_name}",
                'course_title': enrollment.course.title,
                'status': enrollment.status,
                'created_at': enrollment.created_at,
                'price_paid': getattr(enrollment, 'price_paid', None),
            } for enrollment in recent]
            
            # Weekly trend
            week_ago = timezone.now() - timedelta(days=7)
            weekly_enrollments = []
            for i in range(7):
                date = (timezone.now() - timedelta(days=i)).date()
                count = Enrollment.objects.filter(created_at__date=date).count()
                weekly_enrollments.append({
                    'date': date,
                    'count': count
                })
            
            data = {
                "by_status": by_status,
                "by_course": by_course,
                "recent": recent_data,
                "weekly_trend": weekly_enrollments[::-1]  # Reverse to show oldest first
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch enrollment metrics: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ComplaintsMetricsView(APIView):
    """Get detailed complaints metrics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from complaints.models import Complaint
            
            # Complaint statistics
            by_type = list(Complaint.objects.values('type').annotate(count=Count('id')))
            by_status = list(Complaint.objects.values('status').annotate(count=Count('id')))
            by_priority = list(Complaint.objects.values('priority').annotate(count=Count('id')))
            
            # Recent complaints
            recent = Complaint.objects.select_related('student').order_by('-created_at')[:20]
            recent_data = [{
                'id': complaint.id,
                'student_name': f"{complaint.student.first_name} {complaint.student.last_name}",
                'title': complaint.title,
                'type': complaint.type,
                'status': complaint.status,
                'priority': complaint.priority,
                'created_at': complaint.created_at,
            } for complaint in recent]
            
            # Resolution time statistics
            resolved_complaints = Complaint.objects.filter(status='resolved')
            avg_resolution_time = None
            if resolved_complaints.exists():
                # Calculate average resolution time (this would need updated_at - created_at)
                pass
            
            data = {
                "by_type": by_type,
                "by_status": by_status,
                "by_priority": by_priority,
                "recent": recent_data,
                "avg_resolution_time": avg_resolution_time
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch complaints metrics: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class QuizPerformanceView(APIView):
    """Get quiz performance metrics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from quiz.models import QuizAttempt, Quiz
            
            # Quiz performance statistics
            completed_attempts = QuizAttempt.objects.filter(completed_at__isnull=False)
            avg_score = completed_attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0
            
            # Score distribution
            score_ranges = [
                {'range': '90-100', 'count': completed_attempts.filter(score__gte=90).count()},
                {'range': '80-89', 'count': completed_attempts.filter(score__gte=80, score__lt=90).count()},
                {'range': '70-79', 'count': completed_attempts.filter(score__gte=70, score__lt=80).count()},
                {'range': '60-69', 'count': completed_attempts.filter(score__gte=60, score__lt=70).count()},
                {'range': '0-59', 'count': completed_attempts.filter(score__lt=60).count()},
            ]
            
            # Recent attempts
            recent = QuizAttempt.objects.select_related('user', 'quiz').order_by('-started_at')[:20]
            recent_data = [{
                'student_name': f"{attempt.user.first_name} {attempt.user.last_name}",
                'quiz_title': attempt.quiz.title,
                'score': attempt.score,
                'started_at': attempt.started_at,
                'completed_at': attempt.completed_at,
                'time_taken': (attempt.completed_at - attempt.started_at).total_seconds() / 60 if attempt.completed_at else None
            } for attempt in recent]
            
            # Quiz statistics
            total_quizzes = Quiz.objects.count()
            active_quizzes = Quiz.objects.filter(is_active=True).count()
            
            data = {
                "summary": {
                    "total_quizzes": total_quizzes,
                    "active_quizzes": active_quizzes,
                    "total_attempts": QuizAttempt.objects.count(),
                    "completed_attempts": completed_attempts.count(),
                    "avg_score": round(avg_score, 2)
                },
                "score_distribution": score_ranges,
                "recent_attempts": recent_data
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch quiz performance: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FeedbackMetricsView(APIView):
    """Get feedback and rating metrics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from feedback.models import Feedback
            
            # Recent feedback (last 30 days)
            month_ago = timezone.now() - timedelta(days=30)
            recent_feedback = Feedback.objects.filter(created_at__gte=month_ago)
            
            # Average ratings
            avg_ratings = recent_feedback.aggregate(
                teacher=Avg('teacher_rating'),
                material=Avg('material_rating'),
                facilities=Avg('facilities_rating'),
                app=Avg('app_rating')
            )
            
            # Daily rating trends (last 7 days)
            daily_trends = []
            for i in range(7):
                date = (timezone.now() - timedelta(days=i)).date()
                day_feedback = Feedback.objects.filter(created_at__date=date)
                if day_feedback.exists():
                    daily_avg = day_feedback.aggregate(
                        teacher=Avg('teacher_rating'),
                        material=Avg('material_rating'),
                        facilities=Avg('facilities_rating'),
                        app=Avg('app_rating')
                    )
                    daily_trends.append({
                        'date': date,
                        'teacher': round(daily_avg['teacher'] or 0, 2),
                        'material': round(daily_avg['material'] or 0, 2),
                        'facilities': round(daily_avg['facilities'] or 0, 2),
                        'app': round(daily_avg['app'] or 0, 2)
                    })
            
            # Recent feedback details
            recent = Feedback.objects.select_related('student', 'scheduleslot').order_by('-created_at')[:15]
            recent_data = [{
                'student_name': f"{feedback.student.first_name} {feedback.student.last_name}",
                'teacher_rating': feedback.teacher_rating,
                'material_rating': feedback.material_rating,
                'facilities_rating': feedback.facilities_rating,
                'app_rating': feedback.app_rating,
                'total_rating': feedback.total_rating,
                'notes': feedback.notes,
                'created_at': feedback.created_at
            } for feedback in recent]
            
            data = {
                "average_ratings": {
                    "teacher": round(avg_ratings['teacher'] or 0, 2),
                    "material": round(avg_ratings['material'] or 0, 2),
                    "facilities": round(avg_ratings['facilities'] or 0, 2),
                    "app": round(avg_ratings['app'] or 0, 2)
                },
                "daily_trends": daily_trends[::-1],  # Reverse to show oldest first
                "recent_feedback": recent_data,
                "total_feedback_count": Feedback.objects.count()
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch feedback metrics: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RealTimeStatsView(APIView):
    """Get real-time statistics for live updates"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            now = timezone.now()
            today = now.date()
            
            # Real-time counters
            online_users = User.objects.filter(
                last_login__gte=now - timedelta(minutes=15)
            ).count()
            
            recent_activity = {
                "last_hour": {
                    "new_enrollments": Enrollment.objects.filter(
                        created_at__gte=now - timedelta(hours=1)
                    ).count(),
                    "quiz_attempts": QuizAttempt.objects.filter(
                        started_at__gte=now - timedelta(hours=1)
                    ).count(),
                    "new_complaints": Complaint.objects.filter(
                        created_at__gte=now - timedelta(hours=1)
                    ).count(),
                    "feedback_submitted": Feedback.objects.filter(
                        created_at__gte=now - timedelta(hours=1)
                    ).count()
                }
            }
            
            data = {
                "online_users": online_users,
                "recent_activity": recent_activity,
                "server_time": now.isoformat(),
                "today_date": today.isoformat()
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch real-time stats: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FinancialMetricsView(APIView):
    """Get detailed financial metrics and analytics"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from courses.models import Enrollment, Course
            from core.models import Transaction, EWallet
            
            now = timezone.now()
            today = now.date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Revenue Analytics
            total_revenue = Enrollment.objects.filter(
                payment_status__in=['paid', 'partial']
            ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
            
            # Daily revenue for the last 7 days
            daily_revenue = []
            for i in range(7):
                date = today - timedelta(days=i)
                day_revenue = Enrollment.objects.filter(
                    updated_at__date=date,
                    payment_status__in=['paid', 'partial']
                ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
                daily_revenue.append({
                    'date': date,
                    'revenue': float(day_revenue)
                })
            
            # Payment method breakdown
            payment_methods = []
            for method in ['ewallet', 'cash']:
                method_revenue = Enrollment.objects.filter(
                    payment_method=method,
                    payment_status__in=['paid', 'partial']
                ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
                
                method_count = Enrollment.objects.filter(
                    payment_method=method,
                    payment_status__in=['paid', 'partial']
                ).count()
                
                payment_methods.append({
                    'method': method,
                    'revenue': float(method_revenue),
                    'transactions': method_count
                })
            
            # Course revenue ranking
            course_revenue = Enrollment.objects.filter(
                payment_status__in=['paid', 'partial']
            ).values('course__title', 'course__price').annotate(
                revenue=Sum('amount_paid'),
                enrollments=Count('id'),
                completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            ).order_by('-revenue')[:10]
            
            # Outstanding payments analysis
            outstanding_payments = Enrollment.objects.filter(
                status='active',
                payment_status='partial'
            ).annotate(
                outstanding=F('course__price') - F('amount_paid')
            ).aggregate(
                total_outstanding=Sum('outstanding'),
                count=Count('id')
            )
            
            # Revenue by course category
            category_revenue = Enrollment.objects.filter(
                payment_status__in=['paid', 'partial']
            ).values('course__category').annotate(
                revenue=Sum('amount_paid'),
                enrollments=Count('id')
            ).order_by('-revenue')
            
            # Average metrics
            avg_enrollment_value = Enrollment.objects.filter(
                payment_status__in=['paid', 'partial']
            ).aggregate(avg=Avg('amount_paid'))['avg'] or Decimal('0.00')
            
            # Revenue trends (monthly)
            monthly_revenue = []
            for i in range(6):
                month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
                next_month = (month_start + timedelta(days=32)).replace(day=1)
                
                month_rev = Enrollment.objects.filter(
                    updated_at__date__gte=month_start,
                    updated_at__date__lt=next_month,
                    payment_status__in=['paid', 'partial']
                ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
                
                monthly_revenue.append({
                    'month': month_start.strftime('%Y-%m'),
                    'revenue': float(month_rev)
                })
            
            # Transaction volume metrics
            try:
                transaction_stats = Transaction.objects.filter(
                    created_at__gte=month_ago,
                    transaction_type='course_payment',
                    status='completed'
                ).aggregate(
                    total_amount=Sum('amount'),
                    total_count=Count('id'),
                    avg_amount=Avg('amount')
                )
            except:
                transaction_stats = {
                    'total_amount': Decimal('0.00'),
                    'total_count': 0,
                    'avg_amount': Decimal('0.00')
                }
            
            data = {
                "revenue_summary": {
                    "total_revenue": float(total_revenue),
                    "avg_enrollment_value": float(avg_enrollment_value),
                    "outstanding_amount": float(outstanding_payments['total_outstanding'] or 0),
                    "outstanding_count": outstanding_payments['count'] or 0
                },
                "daily_revenue": daily_revenue[::-1],  # Reverse to show oldest first
                "monthly_trends": monthly_revenue[::-1],
                "payment_methods": payment_methods,
                "top_courses_by_revenue": list(course_revenue),
                "revenue_by_category": list(category_revenue),
                "transaction_volume": {
                    "total_amount": float(transaction_stats['total_amount'] or 0),
                    "total_transactions": transaction_stats['total_count'] or 0,
                    "avg_transaction": float(transaction_stats['avg_amount'] or 0)
                }
            }
            
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch financial metrics: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BroadcastUpdateView(APIView):
    """Manually trigger dashboard update broadcast"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if not SupervisorDashboardPermission().has_permission(request, self):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Trigger real-time update to all connected dashboards
            channel_layer = get_channel_layer()
            
            # Get fresh dashboard data
            dashboard_data = {
                "trigger": "manual_refresh",
                "timestamp": timezone.now().isoformat(),
                "updated_by": request.user.get_full_name()
            }
            
            # Broadcast to all connected supervisor dashboards
            async_to_sync(channel_layer.group_send)(
                "supervisor_dashboard",
                {
                    "type": "dashboard_update_broadcast",
                    "data": dashboard_data
                }
            )
            
            return Response(
                {"message": "Dashboard update broadcasted successfully"}, 
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {"error": f"Failed to broadcast update: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )