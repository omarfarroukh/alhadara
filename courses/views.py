from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking,Wishlist, Enrollment
from .serializers import (
    BaseEnrollmentSerializer, DepartmentSerializer, CourseTypeSerializer, CourseSerializer, GuestEnrollmentSerializer,
    HallSerializer, ScheduleSlotSerializer, TeacherScheduleSlotSerializer, BookingSerializer, StudentEnrollmentSerializer,WishlistSerializer,
    HallAvailabilityResponseSerializer
)
from django.db.models import Q, Count, Prefetch,Sum
from core.permissions import IsOwnerOrAdminOrReception,IsStudent,IsTeacher,IsReception,IsAdmin
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.generics import get_object_or_404
from decimal import Decimal, InvalidOperation
from drf_spectacular.utils import extend_schema, OpenApiParameter,OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.openapi import OpenApiExample
from core.models import Interest, StudyField
from datetime import date,time
from django.utils import timezone
from django.conf import settings
import time
import logging
logger = logging.getLogger(__name__)
User = get_user_model()
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy','bulk']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    def list(self, request, *args, **kwargs):
        # Get filtered queryset
        queryset = self.filter_queryset(self.get_queryset())
            
        if not queryset.exists():
                return Response(
                    {'message': 'there are no departments'},
                    status=status.HTTP_200_OK
                )
        return super().list(request, *args, **kwargs)
    
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
    filterset_fields = ['department','department__name']  # Auto-Swagger docs
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

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'interest_id': {'type': 'integer', 'description': 'Interest ID to add'},
                    'study_field_id': {'type': 'integer', 'description': 'Study field ID to add'}
                }
            }
        },
        responses={200: OpenApiResponse(description='Tag added successfully')}
    )
    @action(detail=True, methods=['post'])
    def add_tag(self, request, pk=None):
        """Add interest or study field tag to course type"""
        course_type = self.get_object()
        interest_id = request.data.get('interest_id')
        study_field_id = request.data.get('study_field_id')
        
        if interest_id:
            try:
                interest = Interest.objects.get(id=interest_id)
                course_type.add_interest_tag(interest)
                return Response({'status': 'Interest tag added'})
            except Interest.DoesNotExist:
                return Response({'error': 'Interest not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if study_field_id:
            try:
                study_field = StudyField.objects.get(id=study_field_id)
                course_type.add_study_field_tag(study_field)
                return Response({'status': 'Study field tag added'})
            except StudyField.DoesNotExist:
                return Response({'error': 'Study field not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({'error': 'Provide either interest_id or study_field_id'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'interest_id': {'type': 'integer', 'description': 'Interest ID to remove'},
                    'study_field_id': {'type': 'integer', 'description': 'Study field ID to remove'}
                }
            }
        },
        responses={200: OpenApiResponse(description='Tag removed successfully')}
    )
    @action(detail=True, methods=['post'])
    def remove_tag(self, request, pk=None):
        """Remove interest or study field tag from course type"""
        course_type = self.get_object()
        interest_id = request.data.get('interest_id')
        study_field_id = request.data.get('study_field_id')
        
        if interest_id:
            try:
                interest = Interest.objects.get(id=interest_id)
                course_type.remove_interest_tag(interest)
                return Response({'status': 'Interest tag removed'})
            except Interest.DoesNotExist:
                return Response({'error': 'Interest not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if study_field_id:
            try:
                study_field = StudyField.objects.get(id=study_field_id)
                course_type.remove_study_field_tag(study_field)
                return Response({'status': 'Study field tag removed'})
            except StudyField.DoesNotExist:
                return Response({'error': 'Study field not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({'error': 'Provide either interest_id or study_field_id'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def tags(self, request, pk=None):
        """Get all tags for a course type"""
        course_type = self.get_object()
        return Response(course_type.get_tags())


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
        
        return errors
    
    def get_queryset(self):
        # Base queryset with select_related
        queryset = Course.objects.all().select_related(
            'course_type',
            'department'
        ).prefetch_related(
            'schedule_slots',
            'wishlists'  # Always prefetch for count
        ).annotate(
            wishlist_count=Count('wishlists', distinct=True)
        )        
         # Only add user-specific prefetch if authenticated
        if self.request.user.is_authenticated:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'wishlists',
                    queryset=Wishlist.objects.select_related('owner')
                                        .filter(owner=self.request.user)
                                        .only('id', 'owner'),
                    to_attr='current_user_wishlists'
                )
            )
        else:
            # For anonymous users, set an empty list
            queryset = queryset.prefetch_related(
                Prefetch(
                    'wishlists',
                    queryset=Wishlist.objects.none(),
                    to_attr='current_user_wishlists'
                )
            )
        
        params = self.request.query_params
        
        if department_id := params.get('department'):
            queryset = queryset.filter(department_id=int(department_id))
        if course_type_id := params.get('course_type'):
            queryset = queryset.filter(course_type_id=int(course_type_id))
        if certification := params.get('certification'):
            queryset = queryset.filter(certification_eligible=(certification.lower() == 'true'))
        if category := params.get('category'):
            queryset = queryset.filter(category__iexact=category.lower())
        
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of recommendations (default: 10)',
                required=False
            )
        ],
        responses={200: CourseSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def recommendations(self, request):
        """Get personalized course recommendations based on user interests"""
        limit = int(request.query_params.get('limit', 10))
        recommended_courses = Course.get_recommended_courses(request.user, limit=limit)
        serializer = self.get_serializer(recommended_courses, many=True)
        return Response(serializer.data)

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

    @extend_schema(
        parameters=[
            OpenApiParameter(name='date', description='Date to check availability (YYYY-MM-DD)', required=True, type=OpenApiTypes.DATE),
            OpenApiParameter(name='slot_minutes', description='Slot size in minutes (default 60)', required=False, type=OpenApiTypes.INT),
        ],
        responses={200: HallAvailabilityResponseSerializer}
    )
    @action(detail=True, methods=['get'], url_path='free-slots')
    def free_slots(self, request, pk=None):
        from datetime import datetime, time, timedelta
        hall = self.get_object()
        date_str = request.query_params.get('date')
        slot_minutes = int(request.query_params.get('slot_minutes', 60))
        if not date_str:
            return Response({'error': 'date is required'}, status=400)
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({'error': 'Invalid date format'}, status=400)

        # Define the working hours (customize as needed)
        day_start = time(8, 0)
        day_end = time(22, 0)

        # Gather all bookings and schedule slots for the hall on that date
        bookings = Booking.objects.filter(
            hall=hall,
            start_datetime__date=day,
            status='approved'
        ).order_by('start_datetime')
        slots = ScheduleSlot.objects.filter(
            hall=hall,
            days_of_week__contains=[day.strftime('%a').lower()],
            valid_from__lte=day,
            valid_until__gte=day
        ).order_by('start_time')

        # Build a list of all occupied periods (start, end)
        occupied = []
        for b in bookings:
            occupied.append((b.start_datetime.time(), b.end_datetime.time()))
        for s in slots:
            occupied.append((s.start_time, s.end_time))
        occupied.sort()

        # Merge overlapping occupied periods
        merged = []
        for start, end in sorted(occupied):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)

        # Find free periods between merged occupied periods
        free_periods_data = []
        prev_end = day_start
        for start, end in merged:
            if prev_end < start:
                free_periods_data.append((prev_end, start))
            prev_end = max(prev_end, end)
        if prev_end < day_end:
            free_periods_data.append((prev_end, day_end))

        # For each free period, break into slots
        result_periods = []
        for start, end in free_periods_data:
            slots_data = []
            slot_start = datetime.combine(day, start)
            slot_end = datetime.combine(day, end)
            while slot_start < slot_end:
                next_slot = min(slot_end, slot_start + timedelta(minutes=slot_minutes))
                slots_data.append({'start': slot_start.time(), 'end': next_slot.time()})
                slot_start = next_slot
            result_periods.append({'start': start, 'end': end, 'slots': slots_data})

        response_data = {
            'date': day,
            'hall_id': hall.id,
            'hall_name': hall.name,
            'free_periods': result_periods
        }
        serializer = HallAvailabilityResponseSerializer(response_data)
        return Response(serializer.data)

class ScheduleSlotViewSet(viewsets.ModelViewSet):
    queryset = ScheduleSlot.objects.all().select_related('course', 'hall', 'teacher')
    serializer_class = ScheduleSlotSerializer
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        'course': ['exact'],
        'teacher': ['exact']
    }
    search_fields = ['course__title', 'hall__name', 'teacher__username']
    ordering_fields = ['start_time', 'end_time', 'valid_from', 'valid_until']
    ordering = ['start_time']  # Default ordering by start_time

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsReception()]
        return [permissions.AllowAny()]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('lessons_in_lessons_app')
        params = self.request.query_params
        today = date.today()
        
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
        
        # For specific course filtering
        if course_id := params.get('course'):
            # Check if user is admin or reception
            user = self.request.user
            show_all = user.is_staff or (hasattr(user, 'user_type') and user.user_type == 'reception')
            
            if not show_all:
                # For non-admin/reception users, exclude finished slots and slots with >3 lessons
                queryset = queryset.filter(
                    (Q(valid_until__gte=today) | Q(valid_until__isnull=True)) &
                    ~Q(lessons_in_lessons_app__count__gt=3)
                )
        
        return queryset.distinct()
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Check if we need to filter out fully booked slots
        if request.query_params.get('course'):
            user = request.user
            show_all = user.is_staff or (hasattr(user, 'user_type') and user.user_type == 'reception')
            
            if not show_all:
                # Filter out fully booked slots in Python
                serializer = self.get_serializer(queryset, many=True)
                filtered_data = [
                    slot for slot in serializer.data 
                    if slot['remaining_seats'] > 0
                ]
                
                if not filtered_data:
                    return Response(
                        {'message': 'No available schedule slots found for this course'},
                        status=status.HTTP_200_OK
                    )
                
                return Response(filtered_data)
        
        # Default case
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
          

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Validation failed', 'details': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except serializers.ValidationError as e:
            return Response(
                {'error': 'Validation failed', 'details': e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Optional schedule slot id to filter for a single slot',
                required=False
            ),
            OpenApiParameter(
                name='upcoming_only',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter to only upcoming schedule slots (default: true)',
                required=False
            )
        ],
        responses={200: TeacherScheduleSlotSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_slots(self, request):
        """Get schedule slots associated with the current teacher."""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'This endpoint is only available for teachers'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        today = date.today()
        slot_id = request.query_params.get('id')
        upcoming_only = request.query_params.get('upcoming_only', 'true').lower() == 'true'
        
        # Base queryset with prefetching
        queryset = ScheduleSlot.objects.filter(
            teacher=request.user
        ).select_related('course', 'hall').prefetch_related(
            'lessons_in_lessons_app',
            'enrollments'
        )
        
        # Always exclude expired slots for my_slots endpoint
        queryset = queryset.filter(
            Q(valid_until__gte=today) | Q(valid_until__isnull=True)
        )
        
        # Additional upcoming_only filter if requested
        if upcoming_only:
            queryset = queryset.filter(
                Q(valid_from__gte=today) | Q(valid_from__isnull=True)
            )
        
        # Filter by id if provided
        if slot_id:
            slot = queryset.filter(id=slot_id).first()
            if not slot:
                return Response({'detail': 'Not found or not allowed.'}, status=404)
            serializer = TeacherScheduleSlotSerializer(slot)
            return Response(serializer.data)
        
        # Apply default ordering by valid_from then start_time
        queryset = queryset.order_by('valid_from', 'start_time')
        
        if not queryset.exists():
            return Response(
                {'message': 'No schedule slots found for you'},
                status=status.HTTP_200_OK
            )
            
        serializer = TeacherScheduleSlotSerializer(queryset, many=True)
        return Response(serializer.data)

    
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer # Allow anyone to access
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_datetime', 'status']
    ordering = ['start_datetime']
    
    def get_permissions(self):
        if self.action in ['approve', 'destroy']:
            return [IsReception()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdminOrReception()]
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

class WishlistViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get or create wishlist for the current user
        wishlist, created = Wishlist.objects.get_or_create(
            owner=self.request.user
        )
        return Wishlist.objects.filter(
            owner=self.request.user
        ).prefetch_related(
            Prefetch(
                'courses',
                queryset=Course.objects.select_related(
                    'course_type', 'department'
                )
            )
        )

    @action(detail=False, methods=['post'], url_path='toggle/(?P<course_id>[0-9]+)')
    def toggle_course(self, request, course_id=None):
        try:
            wishlist, created = Wishlist.objects.get_or_create(
                owner=request.user
            )
            course = get_object_or_404(
                Course.objects.prefetch_related(
                    Prefetch(
                        'wishlists',
                        queryset=Wishlist.objects.filter(owner=request.user),
                        to_attr='user_wishlists'
                    )
                ),
                pk=course_id
            )
            
            if course in wishlist.courses.all():
                wishlist.courses.remove(course)
                return Response({
                    "status": "removed",
                    "is_in_wishlist": False,
                    "course_id": course.id
                })
            else:
                wishlist.courses.add(course)
                return Response({
                    "status": "added",
                    "is_in_wishlist": True,
                    "course_id": course.id
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        

class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'course', 'is_guest', 'payment_method']
    search_fields = [
        'course__title', 
        'student__first_name', 'student__last_name',
        'first_name', 'last_name',
        'phone'
    ]
    ordering_fields = ['enrollment_date', 'status']
    ordering = ['-enrollment_date']
    
    def get_serializer_class(self):
        if self.action == 'create_guest':
            return GuestEnrollmentSerializer
        return StudentEnrollmentSerializer
    
    def get_permissions(self):
        if self.action == 'create_guest':
            return [IsReception()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsStudent()]
        if self.action in ['record_cash_payment']:
            return [IsReception()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Enrollment.objects.all().select_related(
            'student', 'course', 'schedule_slot'
        )
        
        if user.is_staff or user.user_type == 'reception':
            return queryset
        elif user.user_type == 'student':
            return queryset.filter(Q(student=user) | Q(enrolled_by=user))
        return Enrollment.objects.none()
    
    

    def perform_create(self, serializer):
        """Create enrollment and process initial payment"""
        try:
            # For regular student enrollments, auto-fill user info
            if not serializer.validated_data.get('is_guest', False):
                user = self.request.user
                serializer.validated_data.update({
                    'student': user,
                    'first_name': user.first_name,
                    'middle_name': user.middle_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'payment_method': 'ewallet'
                })
            
            enrollment = serializer.save()
            
            # Process initial payment (30% of course price)
            initial_payment = (enrollment.course.price * Decimal('0.3')).quantize(Decimal('0.00'))
            try:
                enrollment.process_payment(initial_payment)
            except ValidationError as e:
                enrollment.delete()
                raise serializers.ValidationError(str(e))
                
        except ValidationError as e:
            if 'unique' in str(e):
                raise serializers.ValidationError(
                    "You are already enrolled in this course. Please check your enrollments."
                )
            raise serializers.ValidationError(str(e))

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {
                        'type': 'number',
                        'description': 'Payment amount'
                    }
                },
                'required': ['amount']
            }
        },
        responses={
            200: BaseEnrollmentSerializer,
            400: OpenApiResponse(description='Bad request - invalid amount or insufficient balance')
        }
    )
    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process additional payment from eWallet"""
        enrollment = self.get_object()
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(amount).quantize(Decimal('0.00'))
        except (TypeError, ValueError, InvalidOperation):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        remaining_balance = enrollment.course.price - enrollment.amount_paid
        
        if amount <= 0:
            return Response(
                {'error': 'Payment amount must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount > remaining_balance:
            return Response(
                {
                    'error': f'Payment amount exceeds remaining balance of {remaining_balance}',
                    'remaining_balance': remaining_balance
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            enrollment.process_payment(amount, payment_method='ewallet')
            return Response(self.get_serializer(enrollment).data)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {
                        'type': 'number',
                        'description': 'Cash payment amount'
                    }
                },
                'required': ['amount']
            }
        },
        responses={
            200: BaseEnrollmentSerializer,
            400: OpenApiResponse(description='Bad request - invalid amount')
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[IsReception])
    def record_cash_payment(self, request, pk=None):
        """Record cash payment for an enrollment"""
        enrollment = self.get_object()
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(amount).quantize(Decimal('0.00'))
        except (TypeError, ValueError, InvalidOperation):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Payment amount must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            enrollment.process_payment(amount, payment_method='cash')
            return Response(self.get_serializer(enrollment).data)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        request=None,
        responses={
            200: BaseEnrollmentSerializer,
            400: OpenApiResponse(description='Bad request - enrollment cannot be cancelled')
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel enrollment and process refund"""
        enrollment = self.get_object()
        
        try:
            enrollment.cancel()
            return Response(self.get_serializer(enrollment).data)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    @action(detail=False, methods=['post'], permission_classes=[IsReception])
    def create_guest(self, request):
        """Endpoint for guest enrollments"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get cleaned data (with duplicates removed by serializer)
        validated_data = serializer.validated_data
        
        # Process cash payment if provided
        cash_amount = validated_data.pop('cash_amount', None)
        payment_method = 'cash' if cash_amount else None
        
        try:
            # Create enrollment with single payment_method assignment
            enrollment = Enrollment.objects.create(
                **validated_data,
                is_guest=True,
                payment_method=payment_method,  # Set exactly once here
                enrolled_by=request.user
            )
            
            # Process payment if amount provided
            if cash_amount:
                try:
                    amount = Decimal(str(cash_amount)).quantize(Decimal('0.00'))
                    enrollment.process_payment(amount, payment_method='cash')
                except (ValidationError, InvalidOperation) as e:
                    enrollment.delete()
                    return Response(
                        {'error': f"Payment processing failed: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
        except Exception as e:
            return Response(
                {'error': f"Enrollment creation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            BaseEnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )
        
class UnifiedSearchViewSet(viewsets.ViewSet):
    """
    A unified search viewset that searches across departments, course types, and courses.
    
    Supports:
    - Global search across all models (?search=query)
    - Filtered search by model type (?search=query&models=departments,courses)
    - Course filters: price range, category, certification eligibility
    """
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        operation_id='unified_search',
        summary='Search across departments, course types, and courses',
        description='Search across multiple models simultaneously or filter by specific models',
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query string',
                required=True
            ),
            OpenApiParameter(
                name='models',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Comma-separated list of models to search in. Options: departments, course_types, courses. Leave empty to search all models.',
                required=False
            ),
            OpenApiParameter(
                name='min_price',
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description='Minimum price filter for courses (only applies when searching courses)',
                required=False
            ),
            OpenApiParameter(
                name='max_price',
                type=OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description='Maximum price filter for courses (only applies when searching courses)',
                required=False
            ),
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter courses by category (course or workshop)',
                required=False,
                enum=['course', 'workshop']
            ),
            OpenApiParameter(
                name='certification_eligible',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter courses by certification eligibility (true or false)',
                required=False
            ),
        ],
        responses={
            200: {
                'description': 'Search results containing arrays of matching items from each model'
            },
            400: {'description': 'Bad request - missing or invalid parameters'}
        }
    )
    def list(self, request):
        search_query = request.query_params.get('search', '').strip()
        models_filter = request.query_params.get('models', '').strip()
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        category = request.query_params.get('category')
        certification_eligible = request.query_params.get('certification_eligible')
        
        if not search_query:
            return Response(
                {'error': 'Search query is required. Use ?search=your_query'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate price parameters
        price_filters = {}
        if min_price:
            try:
                price_filters['min_price'] = float(min_price)
                if price_filters['min_price'] < 0:
                    return Response(
                        {'error': 'min_price must be a positive number'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {'error': 'min_price must be a valid number'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if max_price:
            try:
                price_filters['max_price'] = float(max_price)
                if price_filters['max_price'] < 0:
                    return Response(
                        {'error': 'max_price must be a positive number'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {'error': 'max_price must be a valid number'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate price range
        if 'min_price' in price_filters and 'max_price' in price_filters:
            if price_filters['min_price'] > price_filters['max_price']:
                return Response(
                    {'error': 'min_price cannot be greater than max_price'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate category
        if category and category not in ['course', 'workshop']:
            return Response(
                {'error': 'category must be either "course" or "workshop"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate certification_eligible
        course_filters = {}
        if certification_eligible is not None:
            if certification_eligible.lower() in ['true', '1']:
                course_filters['certification_eligible'] = True
            elif certification_eligible.lower() in ['false', '0']:
                course_filters['certification_eligible'] = False
            else:
                return Response(
                    {'error': 'certification_eligible must be true or false'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Parse models filter
        if models_filter:
            allowed_models = {'departments', 'course_types', 'courses'}
            selected_models = set(model.strip() for model in models_filter.split(','))
            
            # Validate selected models
            invalid_models = selected_models - allowed_models
            if invalid_models:
                return Response(
                    {
                        'error': f'Invalid model(s): {", ".join(invalid_models)}. '
                                f'Allowed models: {", ".join(allowed_models)}'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # If no models specified, search in all models
            selected_models = {'departments', 'course_types', 'courses'}
        
        results = {}
        
        # Search in departments
        if 'departments' in selected_models:
            department_results = self._search_departments(search_query)
            results['departments'] = DepartmentSerializer(department_results, many=True).data
        
        # Search in course types
        if 'course_types' in selected_models:
            course_type_results = self._search_course_types(search_query)
            results['course_types'] = CourseTypeSerializer(course_type_results, many=True).data
        
        # Search in courses
        if 'courses' in selected_models:
            course_results = self._search_courses(
                search_query, 
                price_filters,
                category,
                course_filters.get('certification_eligible')
            )
            results['courses'] = CourseSerializer(
                course_results, 
                many=True, 
                context={'request': request}
            ).data
        
        # Check if any results found
        total_results = sum(len(results.get(key, [])) for key in results.keys())
        
        if total_results == 0:
            return Response(
                {
                    'message': f'No results found for "{search_query}"',
                    'searched_models': list(selected_models),
                    **{key: [] for key in selected_models}
                },
                status=status.HTTP_200_OK
            )
        
        return Response(results, status=status.HTTP_200_OK)
    
    def _search_departments(self, query):
        """Search in departments by name and description"""
        return Department.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).order_by('name')
    
    def _search_course_types(self, query):
        """Search in course types by name"""
        return CourseType.objects.select_related('department').filter(
            name__icontains=query
        ).order_by('name')
    
    def _search_courses(self, query, price_filters=None, category=None, certification_eligible=None):
        """Search in courses by title and description with optional filters"""
        queryset = Course.objects.select_related('department', 'course_type').filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
        
        # Apply price filters if provided
        if price_filters:
            if 'min_price' in price_filters:
                queryset = queryset.filter(price__gte=price_filters['min_price'])
            if 'max_price' in price_filters:
                queryset = queryset.filter(price__lte=price_filters['max_price'])
        
        # Apply category filter if provided
        if category:
            queryset = queryset.filter(category=category)
        
        # Apply certification eligibility filter if provided
        if certification_eligible is not None:
            queryset = queryset.filter(certification_eligible=certification_eligible)
        
        return queryset.order_by('title')
    
    # ... (keep the existing suggestions method unchanged)
    @extend_schema(
        operation_id='search_suggestions',
        summary='Get search suggestions',
        description='Get search suggestions based on partial query',
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Partial search query (minimum 2 characters)',
                required=True
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of suggestions per model (default: 5)',
                required=False
            ),
        ]
    )
    @action(detail=False, methods=['get'], url_path='suggestions')
    def suggestions(self, request):
        """
        Get search suggestions for autocomplete functionality
        """
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 5))
        
        if len(query) < 2:
            return Response(
                {'error': 'Query must be at least 2 characters long'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        suggestions = {
            'departments': list(
                Department.objects.filter(
                    Q(name__icontains=query) | Q(description__icontains=query)
                ).values_list('name', flat=True)[:limit]
            ),
            'course_types': list(
                CourseType.objects.filter(
                    name__icontains=query
                ).values_list('name', flat=True)[:limit]
            ),
            'courses': list(
                Course.objects.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                ).values_list('title', flat=True)[:limit]
            )
        }
        
        return Response(suggestions, status=status.HTTP_200_OK)
    