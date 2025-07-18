from rest_framework import generics, status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.response import Response
from .models import ReferralCode, ReferralUsage
from .serializers import ReferralCodeSerializer, ReferralUsageSerializer
from django.contrib.auth import get_user_model
from loyaltypoints.tasks import award_points_task
from rest_framework.permissions import IsAuthenticated
from django.utils.crypto import get_random_string

User = get_user_model()

# Create your views here.

class MyReferralCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code, created = ReferralCode.objects.get_or_create(
            user=request.user,
            defaults={'code': get_random_string(8)}
        )
        return Response(ReferralCodeSerializer(code).data)

class UseReferralCodeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReferralCodeSerializer,   # <-- reuse what you already have
        responses={
            201: OpenApiResponse(description="Referral code used successfully."),
            400: OpenApiResponse(description="Bad request …"),
            404: OpenApiResponse(description="Invalid referral code."),
        },
    )
    def post(self, request):
        code_str = request.data.get('code')
        if not code_str:
            return Response(
                {'detail': 'Referral code is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(request.user, 'used_referral'):
            return Response(
                {'detail': 'You have already used a referral code.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            code = ReferralCode.objects.get(code=code_str)
        except ReferralCode.DoesNotExist:
            return Response(
                {'detail': 'Invalid referral code.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if code.user == request.user:
            return Response(
                {'detail': 'You cannot use your own referral code.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create usage record
        ReferralUsage.objects.create(code=code, used_by=request.user)

        # Award points to both users
        award_points_task.delay(request.user.id, 5, 'Used referral code')
        award_points_task.delay(code.user.id, 5, f'Referral code used by {request.user.id}')

        return Response(
            {'detail': 'Referral code used successfully.'},
            status=status.HTTP_201_CREATED
        )
        
class MyReferralUsagesView(generics.ListAPIView):
    serializer_class = ReferralUsageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            code = self.request.user.referral_code
        except ReferralCode.DoesNotExist:
            return ReferralUsage.objects.none()
        return ReferralUsage.objects.filter(code=code)
