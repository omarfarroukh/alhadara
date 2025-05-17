from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking
from .serializers import (
    DepartmentSerializer, CourseTypeSerializer, CourseSerializer,
    HallSerializer, ScheduleSlotSerializer, BookingSerializer
)
from django.db.models import Q
from core.permissions import IsOwnerOrAdmin,IsStudent,IsTeacher,IsReception,IsAdmin
from django_filters.rest_framework import DjangoFilterBackend

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class CourseTypeViewSet(viewsets.ModelViewSet):
    queryset = CourseType.objects.all().select_related('department')
    serializer_class = CourseTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department']  # Auto-Swagger docs
    search_fields = ['name']
    ordering_fields = ['name']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    def list(self, request, *args, **kwargs):
        department_id = request.query_params.get('department')
        
        # Validate department_id if present
        if department_id:
            try:
                department_id = int(department_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid department ID. Must be an integer.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get filtered queryset
            queryset = self.filter_queryset(self.get_queryset())
            
            if not queryset.exists():
                return Response(
                    {'message': 'No course types found for this department'},
                    status=status.HTTP_200_OK
                )
        
        return super().list(request, *args, **kwargs)


from rest_framework.response import Response
from rest_framework import status

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all().select_related('course_type')
    serializer_class = CourseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['course_type']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'price', 'duration', 'category']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    def list(self, request, *args, **kwargs):
        # Validate parameters
        if errors := self._validate_filters(request):
            return Response(
                {'error': 'Invalid filters', 'details': errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.filter_queryset(self.get_queryset())
        
        if not queryset.exists():  # Check for empty results in all cases
            return Response(
                {'message': 'No courses available'},  # Generic message
                status=status.HTTP_200_OK
            )
        
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Additional validation
        department = serializer.validated_data.get('department')
        course_type = serializer.validated_data.get('course_type')
        
        if course_type.department != department:
            return Response(
                {"error": "Course type must belong to the selected department"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def _validate_filters(self, request):
        """Centralized filter validation"""
        errors = {}
        params = request.query_params
        
        if department_id := params.get('department'):
            if not department_id.isdigit():
                errors['department'] = 'Must be an integer'
        
        if course_type_id := params.get('course_type'):
            if not course_type_id.isdigit():
                errors['course_type'] = 'Must be an integer'
        
        if teacher_id := params.get('teacher'):
            if not teacher_id.isdigit():
                errors['teacher'] = 'Must be an integer'
        
        return errors
    
    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        
        # Apply all filters
        if department_id := params.get('department'):
            queryset = queryset.filter(department_id=int(department_id))
        if course_type_id := params.get('course_type'):
            queryset = queryset.filter(course_type_id=int(course_type_id))
        if teacher_id := params.get('teacher'):
            queryset = queryset.filter(teacher_id=int(teacher_id))
        if certification := params.get('certification'):
            queryset = queryset.filter(certification_eligible=(certification.lower() == 'true'))
        if category := params.get('category'):
            queryset = queryset.filter(category__iexact=category.lower())
        
        return queryset

class HallViewSet(viewsets.ModelViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'location']
    ordering_fields = ['name', 'capacity', 'hourly_rate']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]


from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

class ScheduleSlotViewSet(viewsets.ModelViewSet):
    queryset = ScheduleSlot.objects.all().select_related('course', 'hall')
    serializer_class = ScheduleSlotSerializer
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        'course': ['exact']
    }
    search_fields = ['course__title', 'hall__name']
    ordering_fields = ['start_time', 'end_time', 'valid_from', 'valid_until']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        
        # Day filtering (array containment)
        if day := params.get('day'):
            queryset = queryset.filter(days_of_week__contains=[day.lower()])
        
        # Active on specific date
        if active_date := params.get('active_on'):
            queryset = queryset.filter(
                Q(valid_from__lte=active_date) &
                (Q(valid_until__gte=active_date) | Q(valid_until__isnull=True)))
        
        # Time window filtering
        if start := params.get('start_time'):
            queryset = queryset.filter(end_time__gt=start)
        if end := params.get('end_time'):
            queryset = queryset.filter(start_time__lt=end)
        
        # Department filtering
        if dept_id := params.get('department'):
            queryset = queryset.filter(
                Q(course__department_id=dept_id) |
                Q(hall__department_id=dept_id))
        
        return queryset.distinct()
    
    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Validation failed', 'details': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def list(self, request, *args, **kwargs):
        # Early return for empty queryset
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'No schedule slots found matching your criteria'},
                status=status.HTTP_200_OK
            )
        
        return super().list(request, *args, **kwargs)

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer # Allow anyone to access
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_datetime', 'status']
    ordering = ['start_datetime']
    
    def get_permissions(self):
        if self.action in ['approve', 'destroy']:
            return [IsReception()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        elif self.action == 'create':
            return [permissions.AllowAny()]  # Explicitly allow anyone to create
        return [permissions.AllowAny()]
    
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
    
    @action(detail=True, methods=['post'], permission_classes=[IsReception])
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