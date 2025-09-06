from rest_framework import viewsets,status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.utils import timezone

# Import all the models we need to query
from core.models import Transaction, User
from courses.models import Enrollment, ScheduleSlot, Course, Booking
from complaints.models import Complaint
from feedback.models import Feedback

class DashboardViewSet(viewsets.ViewSet):
    """
    A read-only viewset that provides a flat list of aggregated KPIs for the
    administrative dashboard.
    
    Filter the data by using the `period` query parameter.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Get All Dashboard KPIs",
        description="""
        Provides a comprehensive, single-level JSON object of Key Performance Indicators (KPIs)
        for the admin dashboard. The data can be filtered by a time period.
        
        - Metrics with `_in_period` in their name are calculated for the selected time frame.
        - Metrics with `_current` or `_total` are 'point-in-time' stats and do not change with the date filter.
        
        **Available `period` options:**
        - `today`, `week`, `month` (default), `year`, `custom` (requires `start_date` and `end_date`).
        """,
        parameters=[
            OpenApiParameter(name='period', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, enum=['today', 'week', 'month', 'year', 'custom'], default='month'),
            OpenApiParameter(name='start_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, description='Required if period is "custom".'),
            OpenApiParameter(name='end_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY, description='Required if period is "custom".'),
        ],
        responses={
            200: OpenApiExample(
                'Example Flat Dashboard Response',
                value={
                    "revenue_total_in_period": "1500000.00",
                    "revenue_courses_in_period": "1200000.00",
                    "revenue_bookings_in_period": "300000.00",
                    "refunds_total_in_period": "50000.00",
                    "net_revenue_in_period": "1450000.00",
                    "deposits_sum_in_period": "2000000.00",
                    "deposits_count_in_period": 150,
                    "withdrawals_sum_in_period": "250000.00",
                    "withdrawals_count_in_period": 30,
                    "enrollments_new_in_period": 120,
                    "bookings_new_in_period": 45,
                    "public_bookings_in_period": 35,
                    "private_bookings_in_period": 10,
                    "students_new_in_period": 85,
                    "feedback_new_in_period": 55,
                    "complaints_new_in_period": 8,
                    "complaints_resolved_in_period": 12,
                    "students_total_all_time": 1250,
                    "teachers_total_all_time": 25,
                    "courses_total_all_time": 75,
                    "enrollments_active_current": 450,
                    "students_unverified_current": 15,
                    "complaints_pending_current": 3,
                    "time_period": {
                        "start": "2025-09-01",
                        "end": "2025-09-30",
                        "filter_used": "month"
                    }
                }
            )
        }
    )
    def list(self, request):
        # --- 1. Calculate Date Range ---
        period = request.query_params.get('period', 'month')
        today = timezone.now().date()
        start_date, end_date = None, None

        if period == 'today':
            start_date = end_date = today
        elif period == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)
            end_date = today
        elif period == 'year':
            start_date = today.replace(day=1, month=1)
            end_date = today
        elif period == 'custom':
            try:
                start_date = date.fromisoformat(request.query_params.get('start_date'))
                end_date = date.fromisoformat(request.query_params.get('end_date'))
            except (ValueError, TypeError):
                return Response({"error": "Invalid start_date or end_date. Use YYYY-MM-DD format."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Invalid period parameter."}, status=status.HTTP_400_BAD_REQUEST)

        # --- 2. Define Date Filters ---
        transaction_filter = Q(created_at__date__range=(start_date, end_date))
        enrollment_filter = Q(enrollment_date__date__range=(start_date, end_date))
        user_filter = Q(date_joined__date__range=(start_date, end_date))
        complaint_filter = Q(created_at__date__range=(start_date, end_date))
        booking_filter = Q(date__range=(start_date, end_date))
        feedback_filter = Q(created_at__date__range=(start_date, end_date))

        # --- 3. Perform Aggregations ---
        
        # Financial Metrics (Period-Specific)
        course_revenue = Transaction.objects.filter(transaction_filter, transaction_type='course_payment', status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        booking_revenue = Transaction.objects.filter(transaction_filter, transaction_type='booking_payment', status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_refunds = Transaction.objects.filter(transaction_filter, transaction_type__in=['course_refund', 'booking_refund'], status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        deposits = Transaction.objects.filter(transaction_filter, transaction_type='deposit', status='completed')
        withdrawals = Transaction.objects.filter(transaction_filter, transaction_type='withdrawal', status='completed')
        
        # Activity Metrics (Period-Specific)
        new_enrollments = Enrollment.objects.filter(enrollment_filter).count()
        new_bookings = Booking.objects.filter(booking_filter, status='approved')
        new_students = User.objects.filter(user_filter, user_type='student').count()
        new_feedback = Feedback.objects.filter(feedback_filter).count()
        new_complaints = Complaint.objects.filter(complaint_filter).count()
        resolved_complaints = Complaint.objects.filter(resolved_at__date__range=(start_date, end_date), status='resolved').count()
        
        # "Point-in-Time" Metrics (Not affected by date filter)
        total_students = User.objects.filter(user_type='student').count()
        total_teachers = User.objects.filter(user_type='teacher').count()
        total_courses = Course.objects.count()
        active_enrollments = Enrollment.objects.filter(status='active').count()
        unverified_students = User.objects.filter(user_type='student', is_verified=False).count()
        pending_complaints = Complaint.objects.filter(status__in=['submitted', 'in_review']).count()

        # --- 4. Assemble the Flat Response Dictionary ---
        data = {
            # Financials
            "revenue_total_in_period": f"{(course_revenue + booking_revenue):.2f}",
            "revenue_courses_in_period": f"{course_revenue:.2f}",
            "revenue_bookings_in_period": f"{booking_revenue:.2f}",
            "refunds_total_in_period": f"{total_refunds:.2f}",
            "net_revenue_in_period": f"{(course_revenue + booking_revenue - total_refunds):.2f}",
            "deposits_sum_in_period": f"{(deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')):.2f}",
            "deposits_count_in_period": deposits.count(),
            "withdrawals_sum_in_period": f"{(withdrawals.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')):.2f}",
            "withdrawals_count_in_period": withdrawals.count(),
            
            # Activity in Period
            "enrollments_new_in_period": new_enrollments,
            "bookings_new_in_period": new_bookings.count(),
            "public_bookings_in_period": new_bookings.filter(booking_type='public').count(),
            "private_bookings_in_period": new_bookings.filter(booking_type='private').count(),
            "students_new_in_period": new_students,
            "feedback_new_in_period": new_feedback,
            "complaints_new_in_period": new_complaints,
            "complaints_resolved_in_period": resolved_complaints,

            # Totals & Current State
            "students_total_all_time": total_students,
            "teachers_total_all_time": total_teachers,
            "courses_total_all_time": total_courses,
            "enrollments_active_current": active_enrollments,
            "students_unverified_current": unverified_students,
            "complaints_pending_current": pending_complaints,

            # Time Period Info
            "time_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "filter_used": period
            }
        }

        return Response(data)