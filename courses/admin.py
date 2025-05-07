from django.contrib import admin
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

@admin.register(CourseType)
class CourseTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'department')
    list_filter = ('category', 'department')
    search_fields = ('name',)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'course_type', 'price', 'teacher')
    list_filter = ('department', 'course_type', 'certification_eligible')
    search_fields = ('title', 'teacher__username')

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'location', 'hourly_rate')
    search_fields = ('name', 'location')

class ScheduleSlotAdmin(admin.ModelAdmin):
    list_display = ('course', 'hall', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'hall', 'course')
    search_fields = ('course__title', 'hall__name')

admin.site.register(ScheduleSlot, ScheduleSlotAdmin)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('purpose', 'hall', 'status', 'start_datetime', 'requested_by')
    list_filter = ('purpose', 'status', 'hall')
    search_fields = ('requested_by__username', 'hall__name')
    date_hierarchy = 'start_datetime'