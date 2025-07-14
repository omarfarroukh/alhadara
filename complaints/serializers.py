from rest_framework import serializers
from courses.serializers import StudentEnrollmentSerializer
from .models import Complaint
from courses.models import Enrollment

class ComplaintSerializer(serializers.ModelSerializer):
    """Serializer for student complaint creation and viewing"""
    enrollment_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Complaint
        fields = [
            'id', 'type', 'title', 'description', 'status', 'priority',
            'created_at', 'updated_at', 'enrollment', 'enrollment_details',
            'assigned_to', 'resolution_notes', 'resolved_at'
        ]
        read_only_fields = [
            'id', 'status', 'created_at', 'updated_at', 'assigned_to',
            'resolution_notes', 'resolved_at', 'student'
        ]
        extra_kwargs = {
            'enrollment': {'required': False}
        }
    
    def get_enrollment_details(self, obj):
        """Nested enrollment details"""
        if obj.enrollment:
            return StudentEnrollmentSerializer(obj.enrollment).data
        return None
    
    def validate(self, data):
        complaint_type = data.get('type')
        enrollment = data.get('enrollment')
        
        if complaint_type in ['course', 'teacher'] and not enrollment:
            raise serializers.ValidationError(
                "Enrollment is required for course/teacher complaints"
            )
        if enrollment and enrollment.student != self.context['request'].user:
            raise serializers.ValidationError(
                "You can only complain about your own enrollments"
            )
        return data

class ComplaintResolutionSerializer(serializers.ModelSerializer):
    """Serializer for staff to update complaint resolution"""
    class Meta:
        model = Complaint
        fields = [
            'status', 'priority', 'assigned_to', 'resolution_notes'
        ]
    
    def validate_status(self, value):
        """Validate status transitions"""
        if value == 'resolved' and not self.instance.resolution_notes:
            raise serializers.ValidationError("Resolution notes are required when resolving a complaint")
        return value