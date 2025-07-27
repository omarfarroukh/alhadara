from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json
import asyncio

User = get_user_model()

class SupervisorDashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get user from scope
        self.user = self.scope.get('user')
        
        # Check if user is authenticated and has supervisor privileges
        if not self.user.is_authenticated or self.user.user_type not in ['admin', 'reception']:
            await self.close()
            return
            
        # Join supervisor dashboard group
        self.group_name = "supervisor_dashboard"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Send initial dashboard data
        await self.send_dashboard_update()
        
        # Start periodic updates
        asyncio.create_task(self.periodic_update())

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages from frontend"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'refresh_dashboard':
                await self.send_dashboard_update()
            elif message_type == 'get_detailed_metrics':
                metric_type = data.get('metric_type')
                await self.send_detailed_metrics(metric_type)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")

    async def periodic_update(self):
        """Send dashboard updates every 30 seconds"""
        while True:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds
                await self.send_dashboard_update()
            except Exception as e:
                print(f"Error in periodic update: {e}")
                break

    async def send_dashboard_update(self):
        """Send comprehensive dashboard data"""
        try:
            dashboard_data = await self.get_dashboard_data()
            await self.send(json.dumps({
                "type": "dashboard_update",
                "data": dashboard_data,
                "timestamp": timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f"Failed to fetch dashboard data: {str(e)}")

    async def send_detailed_metrics(self, metric_type):
        """Send detailed metrics for specific type"""
        try:
            detailed_data = await self.get_detailed_metrics_data(metric_type)
            await self.send(json.dumps({
                "type": "detailed_metrics",
                "metric_type": metric_type,
                "data": detailed_data,
                "timestamp": timezone.now().isoformat()
            }))
        except Exception as e:
            await self.send_error(f"Failed to fetch detailed metrics: {str(e)}")

    async def send_error(self, message):
        """Send error message to client"""
        await self.send(json.dumps({
            "type": "error",
            "message": message,
            "timestamp": timezone.now().isoformat()
        }))

    @database_sync_to_async
    def get_dashboard_data(self):
        """Fetch all dashboard metrics"""
        from courses.models import Course, Enrollment, ScheduleSlot
        from quiz.models import Quiz, QuizAttempt
        from complaints.models import Complaint
        from feedback.models import Feedback
        from loyaltypoints.models import LoyaltyPoint
        
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User Statistics
        total_users = User.objects.count()
        active_students = User.objects.filter(
            user_type='student', 
            is_active=True,
            last_login__gte=week_ago
        ).count()
        new_students_today = User.objects.filter(
            user_type='student',
            date_joined__date=today
        ).count()
        new_students_week = User.objects.filter(
            user_type='student',
            date_joined__gte=week_ago
        ).count()
        
        # Course Statistics
        total_courses = Course.objects.count()
        active_courses = Course.objects.filter(is_active=True).count()
        
        # Enrollment Statistics
        total_enrollments = Enrollment.objects.count()
        pending_enrollments = Enrollment.objects.filter(status='pending').count()
        active_enrollments = Enrollment.objects.filter(status='active').count()
        new_enrollments_today = Enrollment.objects.filter(
            created_at__date=today
        ).count()
        
        # Schedule Statistics
        todays_classes = ScheduleSlot.objects.filter(
            date=today,
            is_active=True
        ).count()
        upcoming_classes = ScheduleSlot.objects.filter(
            date__gt=today,
            date__lte=today + timedelta(days=7),
            is_active=True
        ).count()
        
        # Quiz Statistics
        total_quizzes = Quiz.objects.count()
        quiz_attempts_today = QuizAttempt.objects.filter(
            started_at__date=today
        ).count()
        avg_quiz_score = QuizAttempt.objects.filter(
            completed_at__isnull=False
        ).aggregate(avg_score=Avg('score'))['avg_score'] or 0
        
        # Feedback Statistics
        recent_feedback = Feedback.objects.filter(
            created_at__gte=week_ago
        )
        avg_teacher_rating = recent_feedback.aggregate(
            avg_rating=Avg('teacher_rating')
        )['avg_rating'] or 0
        avg_material_rating = recent_feedback.aggregate(
            avg_rating=Avg('material_rating')
        )['avg_rating'] or 0
        avg_facilities_rating = recent_feedback.aggregate(
            avg_rating=Avg('facilities_rating')
        )['avg_rating'] or 0
        avg_app_rating = recent_feedback.aggregate(
            avg_rating=Avg('app_rating')
        )['avg_rating'] or 0
        
        # Complaint Statistics
        total_complaints = Complaint.objects.count()
        pending_complaints = Complaint.objects.filter(
            status__in=['submitted', 'in_review']
        ).count()
        new_complaints_today = Complaint.objects.filter(
            created_at__date=today
        ).count()
        high_priority_complaints = Complaint.objects.filter(
            priority='high',
            status__in=['submitted', 'in_review']
        ).count()
        
        # Revenue/Financial (if loyalty points can indicate revenue)
        try:
            total_loyalty_points = LoyaltyPoint.objects.aggregate(
                total=Count('id')
            )['total'] or 0
            points_earned_today = LoyaltyPoint.objects.filter(
                created_at__date=today,
                transaction_type='earn'
            ).count()
        except:
            total_loyalty_points = 0
            points_earned_today = 0
        
        # System Health Indicators
        unverified_users = User.objects.filter(
            is_verified=False,
            user_type='student'
        ).count()
        
        # Recent Activity
        recent_logins = User.objects.filter(
            last_login__gte=now - timedelta(hours=1)
        ).count()
        
        return {
            "overview": {
                "total_users": total_users,
                "active_students": active_students,
                "total_courses": total_courses,
                "active_courses": active_courses,
                "total_enrollments": total_enrollments,
                "active_enrollments": active_enrollments,
                "recent_logins": recent_logins
            },
            "daily_metrics": {
                "new_students": new_students_today,
                "new_enrollments": new_enrollments_today,
                "todays_classes": todays_classes,
                "quiz_attempts": quiz_attempts_today,
                "new_complaints": new_complaints_today,
                "points_earned": points_earned_today
            },
            "pending_actions": {
                "pending_enrollments": pending_enrollments,
                "pending_complaints": pending_complaints,
                "high_priority_complaints": high_priority_complaints,
                "unverified_users": unverified_users
            },
            "performance_metrics": {
                "avg_quiz_score": round(avg_quiz_score, 2),
                "avg_teacher_rating": round(avg_teacher_rating, 2),
                "avg_material_rating": round(avg_material_rating, 2),
                "avg_facilities_rating": round(avg_facilities_rating, 2),
                "avg_app_rating": round(avg_app_rating, 2)
            },
            "weekly_trends": {
                "new_students": new_students_week,
                "upcoming_classes": upcoming_classes
            },
            "system_status": {
                "total_complaints": total_complaints,
                "total_quizzes": total_quizzes,
                "total_loyalty_points": total_loyalty_points
            }
        }

    @database_sync_to_async
    def get_detailed_metrics_data(self, metric_type):
        """Fetch detailed metrics for specific type"""
        from courses.models import Course, Enrollment, ScheduleSlot
        from quiz.models import QuizAttempt
        from complaints.models import Complaint
        from feedback.models import Feedback
        
        now = timezone.now()
        
        if metric_type == "enrollments":
            return {
                "by_status": list(Enrollment.objects.values('status').annotate(count=Count('id'))),
                "by_course": list(Enrollment.objects.values('course__title').annotate(count=Count('id'))[:10]),
                "recent": list(Enrollment.objects.select_related('student', 'course').order_by('-created_at')[:10].values(
                    'student__first_name', 'student__last_name', 'course__title', 'status', 'created_at'
                ))
            }
        elif metric_type == "complaints":
            return {
                "by_type": list(Complaint.objects.values('type').annotate(count=Count('id'))),
                "by_status": list(Complaint.objects.values('status').annotate(count=Count('id'))),
                "by_priority": list(Complaint.objects.values('priority').annotate(count=Count('id'))),
                "recent": list(Complaint.objects.select_related('student').order_by('-created_at')[:10].values(
                    'student__first_name', 'student__last_name', 'title', 'type', 'status', 'priority', 'created_at'
                ))
            }
        elif metric_type == "quiz_performance":
            return {
                "recent_attempts": list(QuizAttempt.objects.select_related('user', 'quiz').order_by('-started_at')[:10].values(
                    'user__first_name', 'user__last_name', 'quiz__title', 'score', 'started_at', 'completed_at'
                )),
                "score_distribution": list(QuizAttempt.objects.filter(
                    completed_at__isnull=False
                ).extra(
                    select={'score_range': "CASE WHEN score >= 90 THEN '90-100' WHEN score >= 80 THEN '80-89' WHEN score >= 70 THEN '70-79' WHEN score >= 60 THEN '60-69' ELSE '0-59' END"}
                ).values('score_range').annotate(count=Count('id')))
            }
        elif metric_type == "feedback":
            return {
                "rating_trends": list(Feedback.objects.filter(
                    created_at__gte=now - timedelta(days=30)
                ).values('created_at__date').annotate(
                    avg_teacher=Avg('teacher_rating'),
                    avg_material=Avg('material_rating'),
                    avg_facilities=Avg('facilities_rating'),
                    avg_app=Avg('app_rating')
                ).order_by('created_at__date')),
                "recent_feedback": list(Feedback.objects.select_related('student', 'scheduleslot').order_by('-created_at')[:10].values(
                    'student__first_name', 'student__last_name', 'teacher_rating', 'material_rating', 
                    'facilities_rating', 'app_rating', 'notes', 'created_at'
                ))
            }
        
        return {}

    # Group message handlers
    async def dashboard_update_broadcast(self, event):
        """Handle dashboard update broadcasts"""
        await self.send(json.dumps({
            "type": "dashboard_update_broadcast",
            "data": event['data'],
            "timestamp": timezone.now().isoformat()
        }))