# reports/admin.py
from django.contrib import admin
from .models import Report

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'requested_by', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'report_type', 'created_at')
    readonly_fields = ('created_at', 'completed_at', 'job_id', 'error_message', 'parameters', 'file_storage')