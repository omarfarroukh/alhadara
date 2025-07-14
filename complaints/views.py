from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Complaint
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from .serializers import ComplaintSerializer, ComplaintResolutionSerializer
from .tasks import notify_complaint_created_task, notify_complaint_resolved_task
from django_filters.rest_framework import DjangoFilterBackend

class ComplaintViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing complaints.
    """
    queryset = Complaint.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'type', 'priority', 'student']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    
    def get_serializer_class(self):
        if self.request.user.is_superuser and self.action in ['update', 'partial_update', 'resolve']:
            return ComplaintResolutionSerializer
        return ComplaintSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(student=self.request.user)
        return queryset
    @extend_schema(
        request=ComplaintSerializer,
        responses={status.HTTP_201_CREATED: ComplaintSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Queue notification task for new complaints
        notify_complaint_created_task.delay(serializer.instance.id)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        """Set the student to the current user when creating"""
        serializer.save(student=self.request.user)
        
        
    @extend_schema(
        request=ComplaintResolutionSerializer,
        responses={status.HTTP_200_OK: ComplaintResolutionSerializer}
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def resolve(self, request, pk=None):
        """
        Admin endpoint to resolve complaints.
        Requires resolution_notes in payload.
        """
        complaint = self.get_object()
        serializer = self.get_serializer(complaint, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Update complaint
        complaint = serializer.save(
            status='resolved',
            resolved_at=timezone.now(),
            assigned_to=request.user
        )
        
        # Queue resolution notification
        notify_complaint_resolved_task.delay(complaint.id)
        
        return Response(serializer.data)
    
    @extend_schema(
        request=ComplaintResolutionSerializer,
        responses={status.HTTP_200_OK: ComplaintResolutionSerializer}
    )
    def update(self, request, *args, **kwargs):
        """
        Handle status changes during regular updates.
        Only staff can modify status/resolution_notes.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Students can only update description
        if not request.user.is_staff:
            request.data.pop('status', None)
            request.data.pop('resolution_notes', None)
            request.data.pop('priority', None)
            request.data.pop('assigned_to', None)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        complaint = serializer.save()
        
        # Trigger resolution notification if status changed
        if (request.data.get('status') == 'resolved' and 
            instance.status != 'resolved' and 
            complaint.resolution_notes):
            notify_complaint_resolved_task.delay(complaint.id)
        
        return Response(serializer.data)