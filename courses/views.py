from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking
from .serializers import (
    DepartmentSerializer, CourseTypeSerializer, CourseSerializer,
    HallSerializer, ScheduleSlotSerializer, BookingSerializer
)
from django.db.models import Q
from core.permissions import IsAdminUser, IsOwnerOrAdmin,IsStudent,IsTeacher,IsReception,IsAdmin
from django.db import models
from django.db.models import Q

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
    permission_classes = [permissions.AllowAny]  # Allow anyone to access
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_datetime', 'status']
    ordering = ['start_datetime']
    
    def get_permissions(self):
        if self.action in ['approve', 'destroy']:
            return [IsAdminUser()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        elif self.action == 'create':
            return [permissions.AllowAny()]  # Explicitly allow anyone to create
        return [permissions.IsAuthenticatedOrReadOnly()]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if user.is_staff:
                return Booking.objects.all()
            
            if user.user_type == 'teacher':
                return Booking.objects.filter(
                    Q(tutor=user) | 
                    Q(requested_by=user))
            
            if user.user_type == 'student':
                return Booking.objects.filter(
                    Q(student=user) | 
                    Q(requested_by=user))
            
            return Booking.objects.filter(requested_by=user)
        else:
            # For anonymous users, return empty queryset (they can only create)
            return Booking.objects.none()
    
    def perform_create(self, serializer):
        # Set requested_by if user is authenticated
        if self.request.user.is_authenticated:
            serializer.save(requested_by=self.request.user)
        else:
            serializer.save()  # Guest booking with no requested_by
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response({'error': 'Only pending bookings can be approved'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Check for conflicts before approving
        try:
            serializer = self.get_serializer(booking, data={'status': 'approved'}, partial=True)
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        booking.status = 'approved'
        booking.save()
        
        return Response({'status': 'booking approved'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status == 'cancelled':
            return Response({'error': 'Booking is already cancelled'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Allow cancellation by:
        # 1. The person who made the booking (if authenticated)
        # 2. The guest (if they have the booking ID)
        # 3. Admin users
        is_guest_cancellation = (
            not request.user.is_authenticated and 
            str(booking.id) == request.data.get('booking_id')
        )
        
        if not (is_guest_cancellation or 
                booking.requested_by == request.user or 
                request.user.is_staff):
            return Response({'error': 'You can only cancel your own bookings'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        booking.status = 'cancelled'
        booking.save()
        
        return Response({'status': 'booking cancelled'}, status=status.HTTP_200_OK)