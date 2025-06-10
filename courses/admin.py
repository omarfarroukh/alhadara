from django.contrib import admin
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking, Enrollment
from django.contrib.admin import SimpleListFilter
from django.utils.dateformat import time_format
from django import forms
from django.core.exceptions import ValidationError

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')

@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'department')
    list_filter = ['department']
    search_fields = ['name']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'course_type', 'price')
    list_filter = ('department', 'course_type', 'certification_eligible','category')
    search_fields = ('title','category')

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'location', 'hourly_rate')
    search_fields = ('name', 'location')

# Custom filter for days of week
class DaysOfWeekFilter(SimpleListFilter):
    title = 'day of week'
    parameter_name = 'day'
    
    def lookups(self, request, model_admin):
        return ScheduleSlot.DAY_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(days_of_week__contains=[self.value()])
        return queryset
class ScheduleSlotAdminForm(forms.ModelForm):
    class Meta:
        model = ScheduleSlot
        fields = '__all__'
    
    def clean(self):
        """Ensure model validation runs in admin"""
        cleaned_data = super().clean()
        
        # Create a temporary instance to run model validation
        instance = ScheduleSlot(**cleaned_data)
        if self.instance.pk:
            instance.pk = self.instance.pk
        
        try:
            instance.clean()
        except ValidationError as e:
            raise forms.ValidationError(e.message)
        
        return cleaned_data

@admin.register(ScheduleSlot)
class ScheduleSlotAdmin(admin.ModelAdmin):
    form = ScheduleSlotAdminForm
    list_display = ('course', 'teacher_display', 'hall', 'display_days', 'formatted_start_time', 'formatted_end_time', 'valid_from', 'valid_until', 'recurring')
    list_filter = (DaysOfWeekFilter, 'hall', 'course', 'teacher', 'recurring')
    search_fields = ('course__title', 'hall__name', 'teacher__first_name', 'teacher__last_name', 'teacher__phone')
    list_select_related = ('course', 'hall', 'teacher')
    
    def teacher_display(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else "Not assigned"
    teacher_display.short_description = 'Teacher'
    teacher_display.admin_order_field = 'teacher'
    
    def formatted_start_time(self, obj):
        return time_format(obj.start_time, 'H:i')
    formatted_start_time.short_description = 'Start'
    formatted_start_time.admin_order_field = 'start_time'
    
    def formatted_end_time(self, obj):
        return time_format(obj.end_time, 'H:i')
    formatted_end_time.short_description = 'End'
    formatted_end_time.admin_order_field = 'end_time'
    
    def display_days(self, obj):
        return ", ".join([obj.get_day_display(day) for day in obj.days_of_week])
    display_days.short_description = 'Days of Week'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('course', 'hall', 'teacher')
      
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('purpose', 'hall', 'status', 'start_datetime', 'requested_by')
    list_filter = ('purpose', 'status', 'hall')
    search_fields = ('requested_by__username', 'hall__name')
    date_hierarchy = 'start_datetime'

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'payment_status', 'enrollment_date')
    list_filter = ('status', 'payment_status', 'enrollment_date')
    search_fields = ('student__first_name', 'student__last_name', 'course__title')
    readonly_fields = ('enrollment_date',)
    raw_id_fields = ('student', 'course', 'schedule_slot')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student', 'course', 'schedule_slot'
        )