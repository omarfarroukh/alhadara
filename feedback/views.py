from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from .models import Feedback
from .serializers import FeedbackSerializer
from loyaltypoints.tasks import award_points_task
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from datetime import date

# Create your views here.

class FeedbackCreateView(generics.CreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FeedbackSerializer,
        responses={
            201: OpenApiResponse(description="Feedback submitted and points awarded."),
            400: OpenApiResponse(description="Bad request or feedback already exists."),
            403: OpenApiResponse(description="Not allowed to submit feedback for this slot."),
        },
        summary="Submit course feedback and receive loyalty points"
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            scheduleslot = serializer.validated_data['scheduleslot']
            today = date.today()
            # Only allow feedback if the user has a completed enrollment in the slot
            completed_enrollment = scheduleslot.enrollments.filter(student=request.user, status='completed').exists()
            if not completed_enrollment:
                return Response({'detail': 'You can only submit feedback if you have a completed enrollment for this schedule slot.'}, status=status.HTTP_403_FORBIDDEN)
            # Only allow feedback if the slot is finished
            if scheduleslot.valid_until:
                if scheduleslot.valid_until >= today:
                    return Response({'detail': 'Feedback can only be submitted after the schedule slot is finished.'}, status=status.HTTP_403_FORBIDDEN)
            else:
                if scheduleslot.valid_from >= today:
                    return Response({'detail': 'Feedback can only be submitted after the schedule slot is finished.'}, status=status.HTTP_403_FORBIDDEN)
            # Only one feedback per student per slot
            if Feedback.objects.filter(scheduleslot=scheduleslot, student=request.user).exists():
                return Response({'detail': 'Feedback already submitted for this schedule slot.'}, status=status.HTTP_400_BAD_REQUEST)
            feedback = serializer.save(student=request.user)
            award_points_task.delay(request.user.id, 5, 'Submitted course feedback')
            return Response(self.get_serializer(feedback).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FeedbackListByScheduleSlotView(generics.ListAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter('scheduleslot', int, OpenApiParameter.QUERY, required=True, description='ID of the schedule slot'),
        ],
        responses={200: FeedbackSerializer(many=True)},
        summary="List feedback for a specific schedule slot (admin only)"
    )
    def get(self, request, *args, **kwargs):
        scheduleslot_id = request.query_params.get('scheduleslot')
        if not scheduleslot_id:
            return Response({'detail': 'scheduleslot query param is required.'}, status=status.HTTP_400_BAD_REQUEST)
        feedbacks = Feedback.objects.filter(scheduleslot_id=scheduleslot_id)
        avg = self.get_avg_ratings(feedbacks)
        data = self.get_serializer(feedbacks, many=True).data
        return Response({'feedbacks': data, 'averages': avg}, status=status.HTTP_200_OK)

    def get_avg_ratings(self, feedbacks):
        count = feedbacks.count()
        if count == 0:
            return {
                'teacher_rating': None,
                'material_rating': None,    
                'facilities_rating': None,
                'app_rating': None, 
                'total_rating': None,
            }
        return {
            'teacher_rating': round(sum(f.teacher_rating for f in feedbacks) / count, 2),
            'material_rating': round(sum(f.material_rating for f in feedbacks) / count, 2),
            'facilities_rating': round(sum(f.facilities_rating for f in feedbacks) / count, 2),
            'app_rating': round(sum(f.app_rating for f in feedbacks) / count, 2),
            'total_rating': round(sum(f.total_rating for f in feedbacks) / count, 2),
        }
