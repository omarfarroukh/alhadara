from django.contrib import admin
from .models import Complaint
from django.utils import timezone

class PriorityListFilter(admin.SimpleListFilter):
    title = 'priority'
    parameter_name = 'priority'

    def lookups(self, request, model_admin):
        return Complaint.PRIORITY_CHOICES

    def queryset(self, request, queryset):
        if value := self.value():
            return queryset.filter(priority=value)
        return queryset



@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'student', 'type', 'status', 'priority', 'created_at')
    list_filter = ('status', 'type', 'priority', 'created_at') + (PriorityListFilter,)
    search_fields = ('title', 'description', 'student__first_name', 'student__last_name')
    raw_id_fields = ('student', 'enrollment', 'assigned_to')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')
    
    fieldsets = (
        (None, {
            'fields': ('student', 'type', 'title', 'description', 'status', 'priority')
        }),
        ('Related Information', {
            'fields': ('enrollment',),
            'classes': ('collapse',)
        }),
        ('Management', {
            'fields': ('assigned_to', 'resolution_notes', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_resolved', 'mark_as_in_review']
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved', resolved_at=timezone.now())
    mark_as_resolved.short_description = "Mark selected complaints as resolved"
    
    def mark_as_in_review(self, request, queryset):
        queryset.update(status='in_review', assigned_to=request.user)
    mark_as_in_review.short_description = "Mark selected complaints as in review"