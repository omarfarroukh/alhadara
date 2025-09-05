from rest_framework import generics, status
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import LoyaltyPoint, LoyaltyPointLog
from .serializers import LoyaltyConvertRequestSerializer, LoyaltyPointSerializer, TransactionSerializer
from core.models import Transaction, EWallet
from django.db import transaction as db_transaction
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

# Create your views here.

class LoyaltyPointDetailView(generics.RetrieveAPIView):
    queryset = LoyaltyPoint.objects.all()
    serializer_class = LoyaltyPointSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            loyalty = LoyaltyPoint.objects.get(student=request.user)
            serializer = self.get_serializer(loyalty)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except LoyaltyPoint.DoesNotExist:
            return Response({'detail': 'No loyalty points found for this user.', 'points': 0}, status=status.HTTP_200_OK)

class LoyaltyPointToEwalletView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        request=LoyaltyConvertRequestSerializer,
        responses={
            201: TransactionSerializer,
            400: OpenApiResponse(description="Bad request (invalid amount, not enough points, etc.)"),
            404: OpenApiResponse(description="No loyalty points found for this user."),
            500: OpenApiResponse(description="Unexpected server error."),
        },
    )
    def post(self, request):
        try:
            amount = int(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response({'detail': 'Amount must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({'detail': 'Amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with db_transaction.atomic():
                try:
                    loyalty = LoyaltyPoint.objects.select_for_update().get(student=request.user)
                except LoyaltyPoint.DoesNotExist:
                    return Response({'detail': 'No loyalty points found for this user.'}, status=status.HTTP_404_NOT_FOUND)
                if loyalty.points < amount:
                    return Response({'detail': 'Not enough points.'}, status=status.HTTP_400_BAD_REQUEST)
                # Deduct points
                loyalty.points -= amount
                loyalty.save()
                
                LoyaltyPointLog.objects.create(
                    loyalty_account=loyalty,
                    points=-amount, # A negative value
                    reason="Converted to e-wallet balance"
                )
                
                # Deposit to ewallet
                wallet, _ = EWallet.objects.get_or_create(user=request.user)
                try:
                    wallet.deposit(amount)
                except DjangoValidationError as e:
                    return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                # Create transaction
                txn = Transaction.objects.create(
                    sender=None,
                    receiver=request.user,
                    amount=amount,
                    transaction_type='deposit',
                    status='completed',
                    description='Loyalty points transformed to ewallet',
                    reference_id=f'LOYALTY-{request.user.id}-{loyalty.updated_at.timestamp()}'
                )
                return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
