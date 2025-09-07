# reports/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
import django_rq
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiExample
from .models import Report
from .serializers import ReportSerializer, ReportCreateSerializer
from .tasks import (
    generate_financial_report, generate_statistical_report,
    generate_schedule_slot_performance_report, generate_feedback_report,
    generate_complaints_report, generate_student_performance_report
)

REPORT_TASK_MAP = {
    'financial_summary_period': generate_financial_report,
    'statistical_summary_period': generate_statistical_report,
    'schedule_slot_performance': generate_schedule_slot_performance_report,
    'feedback_summary': generate_feedback_report,
    'complaints_summary': generate_complaints_report,
    'student_performance': generate_student_performance_report,
}

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or getattr(user, 'user_type', None) == 'reception':
            return Report.objects.all()
        return Report.objects.filter(requested_by=self.request.user)

    @extend_schema(
        summary="Request a new background report",
        description="""
        Triggers a background job to generate a report. Poll the report's detail endpoint (`/api/reports/{id}/`) to check the status. When `status` is "completed", the `file_details` object will contain a `telegram_download_link`.
        
        **Parameter Requirements:**
        - **Time Period Reports** (`financial_summary_period`, `statistical_summary_period`, `feedback_summary`, `complaints_summary`): Require `start_date` and `end_date`.
        - **Academic Reports** (`schedule_slot_performance`): Requires `schedule_slot_id`.
        """,
        request=ReportCreateSerializer,
        responses={202: ReportSerializer},
        examples=[
            OpenApiExample('Financial Report Request', value={"report_type": "financial_summary_period", "start_date": "2025-08-01", "end_date": "2025-08-31"}, request_only=True),
            OpenApiExample('Statistical Report Request', value={"report_type": "statistical_summary_period", "start_date": "2025-01-01", "end_date": "2025-03-31"}, request_only=True),
            OpenApiExample('Schedule Slot Performance Report Request', value={"report_type": "schedule_slot_performance", "schedule_slot_id": 42}, request_only=True),
        ]
    )
    @action(detail=False, methods=['post'], url_path='create_report', url_name='create_report')
    def create_report(self, request, *args, **kwargs):
        create_serializer = ReportCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        data = create_serializer.validated_data
        report_type = data['report_type']
        
        task_function = REPORT_TASK_MAP.get(report_type)
        if not task_function:
            return Response({'error': 'Invalid report type specified.'}, status=status.HTTP_400_BAD_REQUEST)

        report = Report.objects.create(
            report_type=report_type,
            requested_by=request.user,
            status='pending',
            parameters={k: str(v) for k, v in data.items() if k != 'report_type'}
        )
        
        task_args = [report.id]
        if 'start_date' in data and 'end_date' in data:
            task_args.extend([data['start_date'], data['end_date']])
        elif 'schedule_slot_id' in data:
            task_args.append(data['schedule_slot_id'])

        queue = django_rq.get_queue('default')
        job = queue.enqueue(task_function, *task_args)
        report.job_id = job.id
        report.save()

        serializer = self.get_serializer(report)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)