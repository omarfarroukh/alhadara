from rest_framework import serializers
from .models import Feedback

class FeedbackSerializer(serializers.ModelSerializer):
    total_rating = serializers.FloatField(read_only=True)
    student = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Feedback
        fields = [
            'id', 'scheduleslot', 'student', 'teacher_rating', 'material_rating',
            'facilities_rating', 'app_rating', 'notes', 'created_at', 'total_rating'
        ]
        read_only_fields = ['created_at', 'total_rating', 'student'] 