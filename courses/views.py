from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers
from .models import Department, CourseType, Course, Hall, ScheduleSlot, Booking,Wishlist, Enrollment
from .serializers import (
    DepartmentSerializer, CourseTypeSerializer, CourseSerializer,
    HallSerializer, ScheduleSlotSerializer, BookingSerializer,WishlistSerializer, EnrollmentSerializer
)
from django.db.models import Q
from core.permissions import IsOwnerOrAdminOrReception,IsStudent,IsTeacher,IsReception,IsAdmin
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.generics import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import time
from decimal import Decimal 
from drf_spectacular.utils import extend_schema, OpenApiParameter,OpenApiResponse
from drf_spectacular.types import OpenApiTypes
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
        queryset = super().get_queryset()
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

class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_queryset(self):
        return Wishlist.objects.filter(owner=self.request.user).prefetch_related('courses')

    def perform_create(self, serializer):
        # Ensure each user only has one wishlist
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['post'], url_path='toggle/(?P<course_id>[0-9]+)')
    def toggle_course(self, request, course_id=None):
        """
        Toggle course in user's wishlist
        URL: /api/wishlists/toggle/<course_id>/
        """
        try:
            # Get or create wishlist for current user
            wishlist, created = Wishlist.objects.get_or_create(owner=request.user)
            course = get_object_or_404(Course, pk=course_id)
            
            # Check if course exists in wishlist
            if wishlist.courses.filter(pk=course.id).exists():
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
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'course']
    search_fields = ['course__title', 'student__first_name', 'student__last_name']
    ordering_fields = ['enrollment_date', 'status']
    ordering = ['-enrollment_date']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsStudent()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type == 'reception':
            return Enrollment.objects.all().select_related(
                'student', 'course', 'schedule_slot'
            )
        elif user.user_type == 'student':
            return Enrollment.objects.filter(
                student=user
            ).select_related('course', 'schedule_slot')
        return Enrollment.objects.none()
    
    def perform_create(self, serializer):
        """Create enrollment and process initial payment"""
        enrollment = serializer.save(student=self.request.user)
        
        # Process initial payment (e.g., 20% of course price)
        initial_payment = enrollment.course.price * Decimal('0.2')
        try:
            enrollment.process_payment(initial_payment)
        except ValidationError as e:
            enrollment.delete()  # Rollback enrollment if payment fails
            raise serializers.ValidationError(str(e))
    
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
            amount = Decimal(amount)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate remaining balance
        remaining_balance = enrollment.course.price - enrollment.amount_paid
        
        # Validate payment amount
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
            enrollment.process_payment(amount)
            return Response(self.get_serializer(enrollment).data)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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