from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking,Wishlist, Enrollment,Lesson,Homework,Attendance
from .serializers import (
    BaseEnrollmentSerializer, DepartmentSerializer, CourseTypeSerializer, CourseSerializer, GuestEnrollmentSerializer,
    HallSerializer, ScheduleSlotSerializer, TeacherScheduleSlotSerializer, BookingSerializer, StudentEnrollmentSerializer,WishlistSerializer,
    HallAvailabilityResponseSerializer,LessonSerializer,HomeworkSerializer,ActiveCourseForAdminSerializer,ActiveCourseForTeacherSerializer,
    UnifiedAttendanceSerializer,BulkAttendanceSerializer,ActiveCourseForStudentSerializer,ScheduleSlotSerializer,
    BookingSerializer,StudentEnrollmentSerializer,GuestEnrollmentSerializer,BaseEnrollmentSerializer,
    UnifiedAttendanceSerializer,BulkAttendanceSerializer,ActiveCourseForStudentSerializer,ScheduleSlotSerializer
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
    
    def list(self, request, *args, **kwargs):
        # Early return for empty queryset
        queryset = self.filter_queryset(self.get_queryset())
        if not queryset.exists():
            return Response(
                {'message': 'No schedule slots found matching your criteria'},
                status=status.HTTP_200_OK
            )
        
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[
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
        """Get schedule slots associated with the current teacher"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'This endpoint is only available for teachers'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get teacher's schedule slots with optimized queries
        queryset = ScheduleSlot.objects.filter(
            teacher=request.user
        ).select_related('course', 'hall').prefetch_related(
            'enrollments__student'
        )
        
        # Apply filters
        upcoming_only = request.query_params.get('upcoming_only', 'true').lower() == 'true'
        
        if upcoming_only:
            from django.utils import timezone
            today = timezone.now().date()
            queryset = queryset.filter(
                Q(valid_until__gte=today) | Q(valid_until__isnull=True)
            )
        
        # Apply ordering
        queryset = queryset.order_by('start_time', 'valid_from')
        
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
    
class ActiveCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for active courses.
    
    - Students see their enrolled courses that have started (based on valid_from date)
    - Teachers see courses they are teaching that have started
    - Admins see all active courses with comprehensive information
    - Only returns courses where valid_from <= today
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_active_courses_for_student(self, student):
        """Get active courses for a student based on enrollments and schedule slots"""
        from datetime import date
        
        today = date.today()
        
        # Get enrollments with active schedule slots
        active_enrollments = Enrollment.objects.filter(
            student=student,
            status__in=['pending', 'active'],
            schedule_slot__isnull=False,
            schedule_slot__valid_from__lte=today
        ).select_related(
            'course',
            'course__department',
            'course__course_type',
            'schedule_slot',
            'schedule_slot__hall',
            'schedule_slot__teacher'
        ).filter(
            # Ensure the schedule slot is still valid
            Q(schedule_slot__valid_until__gte=today) | 
            Q(schedule_slot__valid_until__isnull=True)
        )
        
        return active_enrollments
    
    def get_active_courses_for_teacher(self, teacher):
        """Get active courses for a teacher based on schedule slots"""
        from datetime import date
        
        today = date.today()
        
        try:
            active_slots = ScheduleSlot.objects.filter(
                teacher=teacher,
                valid_from__lte=today
            ).filter(
                Q(valid_until__gte=today) | 
                Q(valid_until__isnull=True)
            ).select_related(
                'course',
                'course__department',
                'course__course_type',
                'hall'
            ).prefetch_related(
                'enrollments'
            )
            
            return active_slots
        except Exception as e:
            logger.error(f"Error in get_active_courses_for_teacher: {str(e)}")
            return ScheduleSlot.objects.none()

    def get_all_active_courses_for_admin(self):
        """Get all active courses for admin users with comprehensive information"""
        from datetime import date
        
        today = date.today()
        
        try:
            # Get all active schedule slots with related data
            active_slots = ScheduleSlot.objects.filter(
                valid_from__lte=today
            ).filter(
                Q(valid_until__gte=today) | 
                Q(valid_until__isnull=True)
            ).select_related(
                'course',
                'course__department',
                'course__course_type',
                'hall',
                'teacher'
            ).prefetch_related(
                'enrollments',
                'enrollments__student'
            ).order_by('course__title', 'valid_from')
            
            return active_slots
        except Exception as e:
            logger.error(f"Error in get_all_active_courses_for_admin: {str(e)}")
            return ScheduleSlot.objects.none()

    def get_queryset(self):
        """Return different querysets based on user type"""
        user = self.request.user
        
        if user.user_type == 'student':
            return self.get_active_courses_for_student(user)
        elif user.user_type == 'teacher':
            return self.get_active_courses_for_teacher(user)
        elif user.user_type in ['admin', 'reception']:
            return self.get_all_active_courses_for_admin()
        else:
            return Enrollment.objects.none()
    
    # ... rest of the viewset remains the same ...
    
    def get_serializer_class(self):
        """Return different serializers based on user type"""
        user = self.request.user
        
        if user.user_type == 'student':
            return ActiveCourseForStudentSerializer
        elif user.user_type == 'teacher':
            return ActiveCourseForTeacherSerializer
        elif user.user_type in ['admin', 'reception']:
            return ActiveCourseForAdminSerializer
        else:
            return ActiveCourseForStudentSerializer  # Default
    
    @extend_schema(
        summary='Get active courses',
        description="""
        Get active courses based on user type:
        
        **For Students:**
        - Returns courses they are enrolled in where the course has started (valid_from <= today)
        - Includes enrollment details, payment status, and schedule information
        
        **For Teachers:**
        - Returns courses they are teaching where the course has started (valid_from <= today)
        - Includes enrolled students information and schedule details
        
        **For Admins/Reception:**
        - Returns ALL active courses across the entire system
        - Includes comprehensive information: course details, teacher info, hall info, enrollment statistics
        - Includes financial data: total revenue, pending payments
        - Includes utilization metrics: capacity utilization, enrollment rates
        - Includes detailed student enrollment information
        
        **Active Course Criteria:**
        - Course must have started (schedule_slot.valid_from <= today)
        - Course must not have ended (schedule_slot.valid_until >= today or is null)
        - For students: enrollment status must be 'pending' or 'active'
        - For teachers: they must be assigned as the teacher for the schedule slot
        - For admins: all active courses regardless of teacher or enrollment
        """,
        parameters=[
            OpenApiParameter(
                name='department',
                description='Filter by department name (admin only)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='teacher',
                description='Filter by teacher ID (admin only)',
                required=False,
                type=int
            ),
            OpenApiParameter(
                name='course_type',
                description='Filter by course type (admin only)',
                required=False,
                type=str
            )
        ],
        responses={
            200: OpenApiResponse(
                description='List of active courses',
                examples=[
                    {
                        'admin_example': {
                            'summary': 'Admin Response Example',
                            'value': {
                                'active_courses': [
                                    {
                                        'course_id': 1,
                                        'course_title': 'Python Programming Basics',
                                        'course_description': 'Learn Python programming from scratch',
                                        'course_price': '299.99',
                                        'department_name': 'Computer Science',
                                        'teacher_name': 'John Smith',
                                        'teacher_email': 'john.smith@example.com',
                                        'hall_name': 'Room A101',
                                        'total_enrolled_students': 15,
                                        'active_enrollments': 12,
                                        'pending_enrollments': 3,
                                        'total_revenue': '3899.87',
                                        'pending_payments': '500.13',
                                        'capacity_utilization': 50.0,
                                        'enrollment_rate': 60.0
                                    }
                                ],
                                'count': 1,
                                'summary': {
                                    'total_courses': 25,
                                    'total_students': 487,
                                    'total_revenue': '145,678.50',
                                    'departments': 8,
                                    'teachers': 15
                                }
                            }
                        }
                    }
                ]
            ),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Access forbidden - user type not allowed')
        }
    )
    def list(self, request, *args, **kwargs):
        try:
            user = request.user
            
            # Check user permissions
            if user.user_type not in ['student', 'teacher', 'admin', 'reception']:
                return Response(
                    {
                        'error': 'Access denied',
                        'message': 'This endpoint is only available for students, teachers, and administrators'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            queryset = self.get_queryset()
            
            # Apply admin-specific filters
            if user.user_type in ['admin', 'reception']:
                queryset = self._apply_admin_filters(request, queryset)
            
            if not queryset.exists():
                user_type = user.user_type
                if user_type == 'student':
                    message = 'You have no active courses.'
                elif user_type == 'teacher':
                    message = 'You have no active courses to teach.'
                else:
                    message = 'No active courses found.'
                
                return Response(
                    {
                        'message': message,
                        'active_courses': [],
                        'user_type': user_type,
                        'current_date': date.today().isoformat()
                    },
                    status=status.HTTP_200_OK
                )
            
            serializer = self.get_serializer(queryset, many=True)
            response_data = {
                'active_courses': serializer.data,
                'count': len(serializer.data),
                'user_type': user.user_type,
                'current_date': date.today().isoformat()
            }
            
            # Add summary for admin users
            if user.user_type in ['admin', 'reception']:
                response_data['summary'] = self._get_admin_summary(queryset)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in ActiveCourseViewSet: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'An unexpected error occurred',
                    'details': str(e) if settings.DEBUG else 'Please contact support',
                    'support': 'contact@example.com'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _apply_admin_filters(self, request, queryset):
        """Apply filtering for admin users"""
        department = request.query_params.get('department')
        teacher = request.query_params.get('teacher')
        course_type = request.query_params.get('course_type')
        
        if department:
            queryset = queryset.filter(course__department__name__icontains=department)
        
        if teacher:
            try:
                teacher_id = int(teacher)
                queryset = queryset.filter(teacher_id=teacher_id)
            except ValueError:
                pass  # Invalid teacher ID, ignore filter
        
        if course_type:
            queryset = queryset.filter(course__course_type__name__icontains=course_type)
        
        return queryset
    
    def _get_admin_summary(self, queryset):
        """Generate summary statistics for admin view"""
        from decimal import Decimal
        from collections import defaultdict
        
        total_courses = queryset.count()
        total_students = 0
        total_revenue = Decimal('0')
        departments = set()
        teachers = set()
        
        for slot in queryset:
            student_count = slot.enrollments.filter(
                status__in=['pending', 'active']
            ).count()
            total_students += student_count
            
            revenue = slot.enrollments.filter(
                status__in=['pending', 'active']
            ).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
            total_revenue += revenue
            
            departments.add(slot.course.department.name)
            if slot.teacher:
                teachers.add(slot.teacher.id)
        
        return {
            'total_courses': total_courses,
            'total_students': total_students,
            'total_revenue': str(total_revenue),
            'departments': len(departments),
            'teachers': len(teachers)
        }
    
    @extend_schema(
        summary='Get specific active course details',
        description="""
        Get details of a specific active course by ID.
        
        **For Students:** Returns detailed information about their enrolled course
        **For Teachers:** Returns detailed information about the course they're teaching including student list
        **For Admins:** Returns comprehensive information about any active course
        
        The course must be active (started and not ended) for the user to access it.
        """,
        responses={
            200: OpenApiResponse(description='Active course details'),
            404: OpenApiResponse(description='Active course not found or not accessible'),
            403: OpenApiResponse(description='Access forbidden')
        }
    )
    def retrieve(self, request, pk=None):
        """Retrieve specific active course details"""
        user = request.user
        
        if user.user_type not in ['student', 'teacher', 'admin', 'reception']:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            if user.user_type == 'student':
                # For students, pk is the enrollment ID
                instance = self.get_queryset().get(id=pk)
            else:
                # For teachers and admins, pk is the schedule slot ID
                instance = self.get_queryset().get(id=pk)
                
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
            
        except (Enrollment.DoesNotExist, ScheduleSlot.DoesNotExist):
            return Response(
                {'error': 'Active course not found or you do not have access to it'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        summary='Get active courses statistics',
        description='Get statistics about active courses for the current user',
        responses={
            200: OpenApiResponse(
                description='Statistics about active courses',
                examples=[
                    {
                        'admin_stats': {
                            'summary': 'Admin Statistics',
                            'value': {
                                'total_active_courses': 25,
                                'total_enrolled_students': 487,
                                'total_revenue': '145,678.50',
                                'pending_payments': '12,345.67',
                                'courses_by_department': {
                                    'Computer Science': 8,
                                    'Mathematics': 6,
                                    'Business': 5,
                                    'Arts': 6
                                },
                                'courses_by_type': {
                                    'Programming': 10,
                                    'Theory': 8,
                                    'Practical': 7
                                },
                                'enrollment_statistics': {
                                    'average_students_per_course': 19.5,
                                    'highest_enrolled_course': 35,
                                    'lowest_enrolled_course': 5,
                                    'courses_near_capacity': 3
                                },
                                'financial_overview': {
                                    'average_revenue_per_course': '5,827.14',
                                    'payment_completion_rate': 87.2,
                                    'total_potential_revenue': '167,890.25'
                                }
                            }
                        }
                    }
                ]
            )
        }
    )
    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """Get statistics about active courses"""
        user = request.user
        
        if user.user_type not in ['student', 'teacher', 'admin', 'reception']:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        
        if user.user_type == 'student':
            stats = self._get_student_statistics(queryset)
        elif user.user_type == 'teacher':
            stats = self._get_teacher_statistics(queryset)
        else:  # admin or reception
            stats = self._get_admin_statistics(queryset)
        
        return Response(stats, status=status.HTTP_200_OK)
    
    def _get_student_statistics(self, enrollments):
        """Calculate statistics for student's active courses"""
        from decimal import Decimal
        from collections import defaultdict
        
        total_courses = enrollments.count()
        total_paid = enrollments.aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        
        # Group by department
        dept_counts = defaultdict(int)
        status_counts = defaultdict(int)
        payment_counts = {'fully_paid': 0, 'partially_paid': 0}
        
        for enrollment in enrollments:
            dept_counts[enrollment.course.department.name] += 1
            status_counts[enrollment.status] += 1
            
            if enrollment.amount_paid >= enrollment.course.price:
                payment_counts['fully_paid'] += 1
            else:
                payment_counts['partially_paid'] += 1
        
        return {
            'total_active_courses': total_courses,
            'total_amount_paid': str(total_paid),
            'courses_by_department': dict(dept_counts),
            'courses_by_status': dict(status_counts),
            'payment_summary': payment_counts,
            'current_date': date.today().isoformat()
        }
    
    def _get_teacher_statistics(self, schedule_slots):
        """Calculate statistics for teacher's active courses"""
        from collections import defaultdict
        
        total_courses = schedule_slots.count()
        total_students = 0
        dept_counts = defaultdict(int)
        
        for slot in schedule_slots:
            students_count = slot.enrollments.filter(
                status__in=['pending', 'active']
            ).count()
            total_students += students_count
            dept_counts[slot.course.department.name] += 1
        
        avg_students = total_students / total_courses if total_courses > 0 else 0
        
        return {
            'total_active_courses': total_courses,
            'total_enrolled_students': total_students,
            'courses_by_department': dict(dept_counts),
            'average_students_per_course': round(avg_students, 1),
            'current_date': date.today().isoformat()
        }
    
    def _get_admin_statistics(self, schedule_slots):
        """Calculate comprehensive statistics for admin users"""
        from decimal import Decimal
        from collections import defaultdict
        
        total_courses = schedule_slots.count()
        total_students = 0
        total_revenue = Decimal('0')
        total_pending_payments = Decimal('0')
        total_potential_revenue = Decimal('0')
        
        dept_counts = defaultdict(int)
        type_counts = defaultdict(int)
        enrollment_stats = []
        revenue_stats = []
        
        courses_near_capacity = 0
        fully_paid_enrollments = 0
        total_enrollments = 0
        
        for slot in schedule_slots:
            # Get enrollments for this slot
            enrollments = slot.enrollments.filter(status__in=['pending', 'active'])
            student_count = enrollments.count()
            total_students += student_count
            total_enrollments += student_count
            
            # Revenue calculations
            slot_revenue = enrollments.aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
            total_revenue += slot_revenue
            
            # Calculate pending payments for this slot
            slot_pending = Decimal('0')
            slot_potential = Decimal('0')
            for enrollment in enrollments:
                remaining = enrollment.course.price - enrollment.amount_paid
                slot_pending += max(remaining, Decimal('0'))
                slot_potential += enrollment.course.price
                
                if enrollment.amount_paid >= enrollment.course.price:
                    fully_paid_enrollments += 1
            
            total_pending_payments += slot_pending
            total_potential_revenue += slot_potential
            
            # Department and type counts
            dept_counts[slot.course.department.name] += 1
            type_counts[slot.course.course_type.name] += 1
            
            # Enrollment statistics
            enrollment_stats.append(student_count)
            revenue_stats.append(float(slot_revenue))
            
            # Check capacity utilization
            max_capacity = min(
                slot.course.max_students if slot.course.max_students else float('inf'),
                slot.hall.capacity if slot.hall and slot.hall.capacity else float('inf')
            )
            
            if max_capacity != float('inf') and student_count >= max_capacity * 0.9:
                courses_near_capacity += 1
        
        # Calculate averages and percentages
        avg_students = total_students / total_courses if total_courses > 0 else 0
        avg_revenue = total_revenue / total_courses if total_courses > 0 else Decimal('0')
        payment_completion_rate = (fully_paid_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
        
        enrollment_overview = {
            'average_students_per_course': round(avg_students, 1),
            'highest_enrolled_course': max(enrollment_stats) if enrollment_stats else 0,
            'lowest_enrolled_course': min(enrollment_stats) if enrollment_stats else 0,
            'courses_near_capacity': courses_near_capacity
        }
        
        financial_overview = {
            'average_revenue_per_course': str(round(avg_revenue, 2)),
            'payment_completion_rate': round(payment_completion_rate, 1),
            'total_potential_revenue': str(total_potential_revenue)
        }
        
        return {
            'total_active_courses': total_courses,
            'total_enrolled_students': total_students,
            'total_revenue': str(total_revenue),
            'pending_payments': str(total_pending_payments),
            'courses_by_department': dict(dept_counts),
            'courses_by_type': dict(type_counts),
            'enrollment_statistics': enrollment_overview,
            'financial_overview': financial_overview,
            'current_date': date.today().isoformat(),
            'last_updated': timezone.now().isoformat()
        }
    
    @extend_schema(
        summary='Export active courses data',
        description='Export active courses data in various formats (admin only)',
        parameters=[
            OpenApiParameter(
                name='format',
                description='Export format: csv, excel, pdf',
                required=False,
                type=str,
                default='csv'
            ),
            OpenApiParameter(
                name='include_students',
                description='Include detailed student information',
                required=False,
                type=bool,
                default=False
            )
        ],
        responses={
            200: OpenApiResponse(description='Exported data file'),
            403: OpenApiResponse(description='Access forbidden - admin only'),
        }
    )
    @action(detail=False, methods=['get'], url_path='export')
    def export_data(self, request):
        """Export active courses data (admin only)"""
        user = request.user
        
        if user.user_type not in ['admin', 'reception']:
            return Response(
                {'error': 'Access denied - admin privileges required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        export_format = request.query_params.get('format', 'csv').lower()
        include_students = request.query_params.get('include_students', 'false').lower() == 'true'
        
        try:
            queryset = self.get_queryset()
            
            if export_format == 'csv':
                return self._export_csv(queryset, include_students)
            elif export_format == 'excel':
                return self._export_excel(queryset, include_students)
            elif export_format == 'pdf':
                return self._export_pdf(queryset, include_students)
            else:
                return Response(
                    {'error': 'Invalid format. Supported formats: csv, excel, pdf'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            return Response(
                {'error': 'Export failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_csv(self, queryset, include_students):
        """Export data as CSV"""
        import csv
        from django.http import HttpResponse
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            'Course Title', 'Department', 'Teacher', 'Hall', 'Schedule',
            'Start Date', 'End Date', 'Enrolled Students', 'Total Revenue',
            'Pending Payments', 'Capacity Utilization'
        ]
        
        if include_students:
            headers.extend(['Student Details'])
        
        writer.writerow(headers)
        
        # Write data
        for slot in queryset:
            enrollments = slot.enrollments.filter(status__in=['pending', 'active'])
            student_count = enrollments.count()
            
            revenue = enrollments.aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            
            pending = sum(
                max(e.course.price - e.amount_paid, 0) for e in enrollments
            )
            
            schedule = f"{', '.join(slot.days_of_week)} {slot.start_time}-{slot.end_time}"
            
            capacity_util = 0
            if slot.hall and slot.hall.capacity:
                capacity_util = round((student_count / slot.hall.capacity) * 100, 1)
            
            row = [
                slot.course.title,
                slot.course.department.name,
                slot.teacher.get_full_name() if slot.teacher else 'N/A',
                slot.hall.name if slot.hall else 'N/A',
                schedule,
                slot.valid_from,
                slot.valid_until or 'Ongoing',
                student_count,
                revenue,
                pending,
                f"{capacity_util}%"
            ]
            
            if include_students:
                student_details = '; '.join([
                    f"{e.student.get_full_name()} ({e.status})"
                    for e in enrollments
                ])
                row.append(student_details)
            
            writer.writerow(row)
        
        # Create response
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="active_courses_{date.today()}.csv"'
        return response
    
    def _export_excel(self, queryset, include_students):
        """Export data as Excel (placeholder - requires openpyxl)"""
        return Response(
            {'message': 'Excel export not implemented. Please use CSV format.'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    def _export_pdf(self, queryset, include_students):
        """Export data as PDF (placeholder - requires reportlab)"""
        return Response(
            {'message': 'PDF export not implemented. Please use CSV format.'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )
    
    @extend_schema(
        summary='Get dashboard data for admin',
        description='Get comprehensive dashboard data for admin users including charts and metrics',
        responses={
            200: OpenApiResponse(description='Dashboard data'),
            403: OpenApiResponse(description='Access forbidden - admin only')
        }
    )
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Get dashboard data for admin users"""
        user = request.user
        
        if user.user_type not in ['admin', 'reception']:
            return Response(
                {'error': 'Access denied - admin privileges required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            queryset = self.get_queryset()
            
            # Get basic statistics
            stats = self._get_admin_statistics(queryset)
            
            # Get additional dashboard data
            dashboard_data = {
                'statistics': stats,
                'recent_enrollments': self._get_recent_enrollments(),
                'course_performance': self._get_course_performance(queryset),
                'teacher_workload': self._get_teacher_workload(queryset),
                'hall_utilization': self._get_hall_utilization(queryset),
                'revenue_trends': self._get_revenue_trends(queryset),
                'alerts': self._get_system_alerts(queryset)
            }
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}")
            return Response(
                {'error': 'Failed to load dashboard data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_recent_enrollments(self):
        """Get recent enrollments across all active courses"""
        from datetime import timedelta
        
        recent_date = timezone.now() - timedelta(days=7)
        recent_enrollments = Enrollment.objects.filter(
            enrollment_date__gte=recent_date,
            status__in=['pending', 'active']
        ).select_related(
            'student', 'course', 'schedule_slot'
        ).order_by('-enrollment_date')[:10]
        
        return [
            {
                'student_name': e.student.get_full_name(),
                'course_title': e.course.title,
                'enrollment_date': e.enrollment_date,
                'status': e.status,
                'payment_status': e.payment_status
            }
            for e in recent_enrollments
        ]
    
    def _get_course_performance(self, queryset):
        """Get course performance metrics"""
        performance_data = []
        
        for slot in queryset[:10]:  # Top 10 courses
            enrollments = slot.enrollments.filter(status__in=['pending', 'active'])
            student_count = enrollments.count()
            
            performance_data.append({
                'course_title': slot.course.title,
                'enrolled_students': student_count,
                'max_students': slot.course.max_students,
                'enrollment_rate': round((student_count / slot.course.max_students * 100), 1) if slot.course.max_students else 0,
                'revenue': str(enrollments.aggregate(total=Sum('amount_paid'))['total'] or 0)
            })
        
        return sorted(performance_data, key=lambda x: x['enrolled_students'], reverse=True)
    
    def _get_teacher_workload(self, queryset):
        """Get teacher workload distribution"""
        from collections import defaultdict
        
        teacher_workload = defaultdict(int)
        for slot in queryset:
            if slot.teacher:
                teacher_workload[slot.teacher.get_full_name()] += 1
        
        return [
            {'teacher_name': teacher, 'active_courses': count}
            for teacher, count in sorted(teacher_workload.items(), key=lambda x: x[1], reverse=True)
        ]
    
    def _get_hall_utilization(self, queryset):
        """Get hall utilization statistics"""
        from collections import defaultdict
        
        hall_usage = defaultdict(int)
        for slot in queryset:
            if slot.hall:
                hall_usage[slot.hall.name] += 1
        
        return [
            {'hall_name': hall, 'active_courses': count}
            for hall, count in sorted(hall_usage.items(), key=lambda x: x[1], reverse=True)
        ]
    
    def _get_revenue_trends(self, queryset):
        """Get revenue trends (placeholder for time-based analysis)"""
        # This would typically involve time-series data
        # For now, return basic revenue by department
        from collections import defaultdict
        from decimal import Decimal
        
        dept_revenue = defaultdict(lambda: Decimal('0'))
        
        for slot in queryset:
            revenue = slot.enrollments.filter(
                status__in=['pending', 'active']
            ).aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
            
            dept_revenue[slot.course.department.name] += revenue
        
        return [
            {'department': dept, 'revenue': str(revenue)}
            for dept, revenue in sorted(dept_revenue.items(), key=lambda x: x[1], reverse=True)
        ]
    
    def _get_system_alerts(self, queryset):
        """Get system alerts and notifications"""
        alerts = []
        
        # Check for courses near capacity
        for slot in queryset:
            student_count = slot.enrollments.filter(status__in=['pending', 'active']).count()
            
            if slot.course.max_students and student_count >= slot.course.max_students * 0.9:
                alerts.append({
                    'type': 'warning',
                    'message': f"Course '{slot.course.title}' is near capacity ({student_count}/{slot.course.max_students})",
                    'course_id': slot.course.id,
                    'priority': 'medium'
                })
            
            # Check for courses with many pending payments
            pending_count = slot.enrollments.filter(
                status__in=['pending', 'active'],
                payment_status__in=['pending', 'partial']
            ).count()
            
            if pending_count > 5:
                alerts.append({
                    'type': 'info',
                    'message': f"Course '{slot.course.title}' has {pending_count} students with pending payments",
                    'course_id': slot.course.id,
                    'priority': 'low'
                })
        
        return alerts[:5]  # Return top 5 alerts
                                
class LessonViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing lessons
    
    - Teachers can create, update, delete lessons for their courses
    - Students can view lessons for courses they're enrolled in
    - Admins can view all lessons
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return lessons based on user type"""
        # Handle schema generation case
        if getattr(self, 'swagger_fake_view', False):
            return Lesson.objects.none()
            
        user = self.request.user
        
        if user.user_type == 'teacher':
            # Teachers see lessons they created
            return Lesson.objects.filter(teacher=user).select_related(
                'course', 'schedule_slot', 'teacher'
            ).prefetch_related('homework_assignments', 'attendance_records')
        
        elif user.user_type == 'student':
            # Students see lessons for courses they're enrolled in
            from .models import Enrollment  # Adjust import as needed
            enrolled_courses = Enrollment.objects.filter(
                student=user,
                status__in=['pending', 'active']
            ).values_list('course_id', flat=True)
            
            return Lesson.objects.filter(
                course_id__in=enrolled_courses
            ).select_related(
                'course', 'schedule_slot', 'teacher'
            ).prefetch_related('homework_assignments', 'attendance_records')
        
        elif user.user_type in ['admin', 'reception']:
            # Admins see all lessons
            return Lesson.objects.all().select_related(
                'course', 'schedule_slot', 'teacher'
            ).prefetch_related('homework_assignments', 'attendance_records')
        
        return Lesson.objects.none()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on user type"""
        # Handle schema generation case
        if getattr(self, 'swagger_fake_view', False):
            return LessonSerializer
            
        return LessonSerializer
    
    def perform_create(self, serializer):
        """Set teacher to current user when creating lesson"""
        serializer.save(teacher=self.request.user)
    
    @extend_schema(
        summary='Create a new lesson',
        description="""
        Create a new lesson. Only teachers can create lessons.
        The teacher field will be automatically set to the current user.
        """,
        request=LessonSerializer,
        responses={
            201: LessonSerializer,
            400: 'Bad Request - Validation errors',
            403: 'Forbidden - Only teachers can create lessons'
        }
    )
    def create(self, request, *args, **kwargs):
        """Create a new lesson"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'Only teachers can create lessons'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        summary='List lessons',
        description="""
        Get lessons based on user type:
        - Teachers: Lessons they created
        - Students: Lessons for enrolled courses
        - Admins: All lessons
        """,
        parameters=[
            OpenApiParameter(name='course', description='Filter by course ID', required=False, type=int),
            OpenApiParameter(name='status', description='Filter by lesson status', required=False, type=str),
            OpenApiParameter(name='lesson_date', description='Filter by lesson date (YYYY-MM-DD)', required=False, type=str)
        ]
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Apply filters
        course_id = request.query_params.get('course')
        status_filter = request.query_params.get('status')
        lesson_date = request.query_params.get('lesson_date')
        
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if lesson_date:
            queryset = queryset.filter(lesson_date=lesson_date)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'lessons': serializer.data,
            'count': len(serializer.data),
            'user_type': request.user.user_type
        })
    
    @extend_schema(
        summary='Update a lesson',
        description='Update an existing lesson. Only the lesson creator can update it.',
        request=LessonSerializer,
        responses={
            200: LessonSerializer,
            400: 'Bad Request - Validation errors',
            403: 'Forbidden - Not the lesson creator',
            404: 'Not Found'
        }
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        summary='Partially update a lesson',
        description='Partially update an existing lesson. Only the lesson creator can update it.',
        request=LessonSerializer,
        responses={
            200: LessonSerializer,
            400: 'Bad Request - Validation errors',
            403: 'Forbidden - Not the lesson creator',
            404: 'Not Found'
        }
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @extend_schema(
        summary='Get lesson details',
        description='Get detailed information about a specific lesson',
        responses={
            200: LessonSerializer,
            404: 'Not Found'
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary='Delete a lesson',
        description='Delete a lesson. Only the lesson creator can delete it.',
        responses={
            204: 'No Content - Successfully deleted',
            403: 'Forbidden - Not the lesson creator',
            404: 'Not Found'
        }
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    
    @extend_schema(
        summary='Get lessons for a specific course',
        description='Get all lessons for a specific course (if user has access)'
    )
    @action(detail=False, methods=['get'], url_path='by-course/(?P<course_id>[^/.]+)')
    def by_course(self, request, course_id=None):
        """Get lessons for a specific course"""
        queryset = self.get_queryset().filter(course_id=course_id)
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'course_id': course_id,
            'lessons': serializer.data,
            'count': len(serializer.data)
        })
    
    @extend_schema(
        summary='Create multiple lessons at once',
        description='Allow teachers to create multiple lessons for a course',
        request={
            'type': 'object',
            'properties': {
                'lessons': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'title': {'type': 'string'},
                            'notes': {'type': 'string'},
                            'course': {'type': 'integer'},
                            'schedule_slot': {'type': 'integer'},
                            'lesson_order': {'type': 'integer'},
                            'lesson_date': {'type': 'string', 'format': 'date'},
                            'duration_minutes': {'type': 'integer'},
                            'status': {'type': 'string', 'enum': ['scheduled', 'in_progress', 'completed', 'cancelled']}
                        }
                    }
                }
            },
            'required': ['lessons']
        },
        examples=[
            OpenApiExample(
                'Bulk Create Example',
                value={
                    'lessons': [
                        {
                            'title': 'Introduction to Python',
                            'notes': 'Basic Python concepts',
                            'course': 1,
                            'schedule_slot': 1,
                            'lesson_order': 1,
                            'lesson_date': '2024-01-15',
                            'duration_minutes': 90,
                            'status': 'scheduled'
                        }
                    ]
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple lessons at once"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'Only teachers can create lessons'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        lessons_data = request.data.get('lessons', [])
        if not lessons_data:
            return Response(
                {'error': 'No lessons data provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_lessons = []
        errors = []
        
        for i, lesson_data in enumerate(lessons_data):
            serializer = LessonSerializer(data=lesson_data, context={'request': request})
            if serializer.is_valid():
                lesson = serializer.save(teacher=request.user)
                created_lessons.append(serializer.data)
            else:
                errors.append({
                    'index': i,
                    'errors': serializer.errors
                })
        
        return Response({
            'created': len(created_lessons),
            'lessons': created_lessons,
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_lessons else status.HTTP_400_BAD_REQUEST)

class HomeworkViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Homework without submission functionality
    """
    serializer_class = HomeworkSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['course', 'lesson', 'status']
    
    def get_queryset(self):
        """Return appropriate homework based on user type"""
        user = self.request.user
        
        base_queryset = Homework.objects.select_related(
            'lesson', 'course', 'teacher'
        )
        
        if user.user_type == 'teacher':
            return base_queryset.filter(teacher=user)
        
        elif user.user_type == 'student':
            enrolled_courses = Enrollment.objects.filter(
                student=user,
                status__in=['pending', 'active']
            ).values_list('course_id', flat=True)
            
            return base_queryset.filter(
                course_id__in=enrolled_courses,
                status='published'
            ).exclude(deadline__lt=timezone.now())  # This excludes expired homework
        
        elif user.user_type in ['admin', 'reception']:
            return base_queryset
        
        return Homework.objects.none()

    def perform_create(self, serializer):
        """Auto-set teacher and course when creating homework"""
        serializer.save(
            teacher=self.request.user,
            course=serializer.validated_data['lesson'].course,
            status='published'
        )

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue homework assignments"""
        queryset = self.filter_queryset(self.get_queryset())
        overdue_hw = queryset.filter(deadline__lt=timezone.now())
        serializer = self.get_serializer(overdue_hw, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming homework assignments"""
        queryset = self.filter_queryset(self.get_queryset())
        upcoming_hw = queryset.filter(deadline__gte=timezone.now())
        serializer = self.get_serializer(upcoming_hw, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        """List homework with filtering options"""
        queryset = self.filter_queryset(self.get_queryset())
        
        lesson_id = request.query_params.get('lesson')
        overdue_filter = request.query_params.get('overdue')
        
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        
        if overdue_filter == 'true':
            queryset = queryset.filter(deadline__lt=timezone.now())
        elif overdue_filter == 'false':
            queryset = queryset.filter(deadline__gte=timezone.now())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Simplified ViewSet using the unified serializer
    """
    serializer_class = UnifiedAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Attendance.objects.select_related(
            'student', 'course', 'lesson', 'teacher'
        )
        
        if user.user_type == 'teacher':
            return queryset.filter(teacher=user)
        elif user.user_type == 'student':
            return queryset.filter(student=user)
        elif user.user_type in ['admin', 'reception']:
            return queryset
        return Attendance.objects.none()

    def perform_create(self, serializer):
        """Auto-set teacher when creating records"""
        serializer.save(teacher=self.request.user)

    @extend_schema(
        summary='Create attendance record',
        description="""
        Create a new attendance record for a student in a lesson.
        The teacher field is automatically set to the current user.
        """,
        request=UnifiedAttendanceSerializer,
        responses={201: UnifiedAttendanceSerializer}
    )
    def create(self, request, *args, **kwargs):
        """Create attendance record with proper validation"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'Only teachers can create attendance records'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(name='student', description='Filter by student ID', required=False, type=int),
            OpenApiParameter(name='date_after', description='Filter records after date (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='date_before', description='Filter records before date (YYYY-MM-DD)', required=False, type=str)
        ]
    )
    def list(self, request, *args, **kwargs):
        """List attendance records with enhanced filtering"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Additional filters
        student_id = request.query_params.get('student')
        date_after = request.query_params.get('date_after')
        date_before = request.query_params.get('date_before')
        
        if student_id and request.user.user_type in ['teacher', 'admin']:
            queryset = queryset.filter(student_id=student_id)
        
        if date_after:
            queryset = queryset.filter(lesson__lesson_date__gte=date_after)
        if date_before:
            queryset = queryset.filter(lesson__lesson_date__lte=date_before)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'attendance_records': serializer.data,
            'count': len(serializer.data),
            'user_type': request.user.user_type
        })

    @extend_schema(
        summary='Get lesson attendance',
        description='Get all attendance records for a specific lesson',
        parameters=[
            OpenApiParameter(name='detailed', description='Include full student details', required=False, type=bool)
        ]
    )
    @action(detail=False, methods=['get'], url_path='by-lesson/(?P<lesson_id>[^/.]+)')
    def by_lesson(self, request, lesson_id=None):
        """Get attendance for specific lesson with optional detail level"""
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        queryset = self.get_queryset().filter(lesson_id=lesson_id)
        
        if not detailed and request.user.user_type == 'teacher':
            # Optimized response for teacher roster view
            roster_data = queryset.values(
                'student__id',
                'student__first_name',
                'student__last_name',
                'attendance'
            )
            return Response({
                'lesson_id': lesson_id,
                'attendance_roster': list(roster_data),
                'count': len(roster_data)
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'lesson_id': lesson_id,
            'attendance_records': serializer.data,
            'count': len(serializer.data)
        })

    @extend_schema(
        request=BulkAttendanceSerializer,
        responses={201: OpenApiTypes.OBJECT}
    )
    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request):
        """Create multiple attendance records at once"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'Only teachers can record attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BulkAttendanceSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "overall_stats": {
                        "type": "object",
                        "properties": {
                            "total_lessons": {"type": "integer"},
                            "present_count": {"type": "integer"},
                            "absent_count": {"type": "integer"},
                            "attendance_rate": {"type": "number"}
                        }
                    },
                    "student_stats": {"type": "array"}
                }
            }
        }
    )
    @action(detail=False, methods=['get'], url_path='stats/(?P<course_id>[^/.]+)')
    def course_stats(self, request, course_id=None):
        """Get detailed attendance statistics for a course"""
        if request.user.user_type != 'teacher':
            return Response(
                {'error': 'Only teachers can view attendance statistics'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.db.models import Count, Q, F, ExpressionWrapper, FloatField
        from django.db.models.functions import Coalesce

        # Get base queryset
        queryset = self.get_queryset().filter(course_id=course_id)
        
        # Overall statistics
        total_lessons = Lesson.objects.filter(
            course_id=course_id,
            status__in=['completed', 'in_progress']
        ).count()
        
        present_count = queryset.filter(attendance='present').count()
        absent_count = queryset.filter(attendance='absent').count()
        
        # Student-level statistics
        student_stats = queryset.values(
            'student__id',
            'student__first_name',
            'student__last_name'
        ).annotate(
            total_attended=Count('id', filter=Q(attendance='present')),
            attendance_rate=ExpressionWrapper(
                Coalesce(
                    Count('id', filter=Q(attendance='present')) * 100.0 / 
                    F('total_lessons'),
                    0
                ),
                output_field=FloatField()
            )
        ).order_by('-attendance_rate', 'student__last_name')
        
        return Response({
            'course_id': course_id,
            'overall_stats': {
                'total_lessons': total_lessons,
                'present_count': present_count,
                'absent_count': absent_count,
                'attendance_rate': round((present_count / (present_count + absent_count) * 100, 2)) if (present_count + absent_count) > 0 else 0
            },
            'student_stats': list(student_stats)
        })

    def get_serializer_context(self):
        """Add request and view action to serializer context"""
        context = super().get_serializer_context()
        context.update({
            'request': self.request,
            'view': self
        })
        return context