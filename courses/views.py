from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking
from .serializers import (
    DepartmentSerializer, CourseTypeSerializer, CourseSerializer,
    HallSerializer, ScheduleSlotSerializer, BookingSerializer
)
from core.permissions import IsAdminUser, IsOwnerOrAdmin


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class CourseTypeViewSet(viewsets.ModelViewSet):
    queryset = CourseType.objects.all()
    serializer_class = CourseTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'category']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = CourseType.objects.all()
        department_id = self.request.query_params.get('department', None)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'price', 'duration']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = Course.objects.all()
        department_id = self.request.query_params.get('department', None)
        course_type_id = self.request.query_params.get('course_type', None)
        teacher_id = self.request.query_params.get('teacher', None)
        certification = self.request.query_params.get('certification', None)
        
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if course_type_id:
            queryset = queryset.filter(course_type_id=course_type_id)
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        if certification:
            queryset = queryset.filter(certification_eligible=(certification.lower() == 'true'))
        
        return queryset


class HallViewSet(viewsets.ModelViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location']
    ordering_fields = ['name', 'capacity', 'hourly_rate']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class ScheduleSlotViewSet(viewsets.ModelViewSet):
    queryset = ScheduleSlot.objects.all()
    serializer_class = ScheduleSlotSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['day_of_week', 'start_time']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        queryset = ScheduleSlot.objects.all()
        course_id = self.request.query_params.get('course', None)
        hall_id = self.request.query_params.get('hall', None)
        day = self.request.query_params.get('day', None)
        
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        if hall_id:
            queryset = queryset.filter(hall_id=hall_id)
        if day:
            queryset = queryset.filter(day_of_week=day)
        
        return queryset


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_datetime', 'status']
    ordering = ['start_datetime']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Booking.objects.all()
        
        if user.user_type == 'teacher':
            return Booking.objects.filter(tutor=user) | Booking.objects.filter(requested_by=user)
        
        if user.user_type == 'student':
            return Booking.objects.filter(student=user) | Booking.objects.filter(requested_by=user)
        
        return Booking.objects.filter(requested_by=user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response({'error': 'Only pending bookings can be approved'}, status=status.HTTP_400_BAD_REQUEST)
        
        booking.status = 'approved'
        booking.save()
        
        return Response({'status': 'booking approved'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status == 'cancelled':
            return Response({'error': 'Booking is already cancelled'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Only allow admins to cancel approved bookings or the requester to cancel their own pending bookings
        if booking.status == 'approved' and not request.user.is_staff:
            return Response({'error': 'Only administrators can cancel approved bookings'}, status=status.HTTP_403_FORBIDDEN)
        
        if booking.requested_by != request.user and not request.user.is_staff:
            return Response({'error': 'You can only cancel your own bookings'}, status=status.HTTP_403_FORBIDDEN)
        
        booking.status = 'cancelled'
        booking.save()
        
        return Response({'status': 'booking cancelled'}, status=status.HTTP_200_OK)