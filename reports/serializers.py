from rest_framework import serializers
from .models import Report
from core.serializers import FileStorageSerializer

class ReportSerializer(serializers.ModelSerializer):
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    file_details = FileStorageSerializer(source='file_storage', read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'report_type_display', 'requested_by', 'requested_by_name',
            'status', 'status_display', 'file_details', 'job_id', 'error_message',
            'parameters', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'status', 'job_id', 'error_message', 'created_at', 'completed_at', 'parameters', 'file_details']

class ReportCreateSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=Report.REPORT_TYPE_CHOICES)
    start_date = serializers.DateField(required=False, help_text="YYYY-MM-DD")
    end_date = serializers.DateField(required=False, help_text="YYYY-MM-DD")
    schedule_slot_id = serializers.IntegerField(required=False)

    def validate(self, data):
        report_type = data.get('report_type')
        if report_type in ['financial_summary_period', 'statistical_summary_period', 'feedback_summary', 'complaints_summary']:
            if not data.get('start_date') or not data.get('end_date'):
                raise serializers.ValidationError("Start and end dates are required for this report type.")
            if data['start_date'] > data['end_date']:
                 raise serializers.ValidationError("Start date cannot be after end date.")
        if report_type == 'schedule_slot_performance' and not data.get('schedule_slot_id'):
            raise serializers.ValidationError("A schedule_slot_id is required for this report type.")
        return data