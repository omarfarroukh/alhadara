from django.contrib import admin
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking
from django.contrib.admin import SimpleListFilter

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
    list_display = ('title', 'department', 'course_type', 'price', 'teacher')
    list_filter = ('department', 'course_type', 'certification_eligible','category')
    search_fields = ('title', 'teacher__username','category')

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

@admin.register(ScheduleSlot)
class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = ('course', 'hall', 'display_days', 'start_time', 'end_time')
    list_filter = (DaysOfWeekFilter, 'hall', 'course', 'recurring')
    search_fields = ('course__title', 'hall__name')
    
    def display_days(self, obj):
        return ", ".join([obj.get_day_display(day) for day in obj.days_of_week])
    display_days.short_description = 'Days of Week'

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('purpose', 'hall', 'status', 'start_datetime', 'requested_by')
    list_filter = ('purpose', 'status', 'hall')
    search_fields = ('requested_by__username', 'hall__name')
    date_hierarchy = 'start_datetime'