from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest
)
from .serializers import (
    SecurityQuestionSerializer, SecurityAnswerSerializer, InterestSerializer, 
    ProfileSerializer, ProfileDetailSerializer, EWalletSerializer, DepositMethodSerializer,
    BankTransferInfoSerializer, MoneyTransferInfoSerializer, DepositRequestSerializer
)
from .permissions import IsAdminUser, IsOwnerOrAdmin


class SecurityQuestionViewSet(viewsets.ModelViewSet):
    queryset = SecurityQuestion.objects.all()
    serializer_class = SecurityQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['question_text']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class SecurityAnswerViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityAnswerSerializer
    permission_classes = [IsOwnerOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SecurityAnswer.objects.all()
        return SecurityAnswer.objects.filter(user=user)


class InterestViewSet(viewsets.ModelViewSet):
    queryset = Interest.objects.all()
    serializer_class = InterestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'category']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]


class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name', 'user__username']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Profile.objects.all()
        return Profile.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return ProfileDetailSerializer
        return ProfileSerializer

    @action(detail=True, methods=['post'])
    def add_interest(self, request, pk=None):
        profile = self.get_object()
        interest_id = request.data.get('interest')
        intensity = request.data.get('intensity', 3)
        
        if not interest_id:
            return Response({'error': 'Interest ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            interest = Interest.objects.get(id=interest_id)
            profile_interest, created = ProfileInterest.objects.get_or_create(
                profile=profile,
                interest=interest,
                defaults={'intensity': intensity}
            )
            
            if not created:
                profile_interest.intensity = intensity
                profile_interest.save()
                
            return Response({'status': 'interest added'}, status=status.HTTP_200_OK)
        except Interest.DoesNotExist:
            return Response({'error': 'Interest not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def remove_interest(self, request, pk=None):
        profile = self.get_object()
        interest_id = request.data.get('interest')
        
        if not interest_id:
            return Response({'error': 'Interest ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            profile_interest = ProfileInterest.objects.get(profile=profile, interest_id=interest_id)
            profile_interest.delete()
            return Response({'status': 'interest removed'}, status=status.HTTP_200_OK)
        except ProfileInterest.DoesNotExist:
            return Response({'error': 'Interest not found for this profile'}, status=status.HTTP_404_NOT_FOUND)


class EWalletViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EWalletSerializer
    permission_classes = [IsOwnerOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return EWallet.objects.all()
        return EWallet.objects.filter(user=user)


class DepositMethodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepositMethod.objects.filter(is_active=True)
    serializer_class = DepositMethodSerializer
    permission_classes = [permissions.IsAuthenticated]


class DepositRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DepositRequestSerializer
    permission_classes = [IsOwnerOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return DepositRequest.objects.all()
        return DepositRequest.objects.filter(user=user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        deposit_request = self.get_object()
        
        if deposit_request.status != 'pending':
            return Response({'error': 'Only pending requests can be approved'}, status=status.HTTP_400_BAD_REQUEST)
        
        wallet = deposit_request.wallet
        wallet.current_balance += deposit_request.amount
        wallet.save()
        
        deposit_request.status = 'verified'
        deposit_request.save()
        
        return Response({'status': 'deposit approved'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        deposit_request = self.get_object()
        
        if deposit_request.status != 'pending':
            return Response({'error': 'Only pending requests can be rejected'}, status=status.HTTP_400_BAD_REQUEST)
        
        deposit_request.status = 'rejected'
        deposit_request.save()
        
        return Response({'status': 'deposit rejected'}, status=status.HTTP_200_OK)