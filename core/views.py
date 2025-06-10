from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema,OpenApiExample, OpenApiResponse
from django.utils.crypto import get_random_string
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from .throttles import LoginRateThrottle
from drf_spectacular.types import OpenApiTypes
from rest_framework.generics import RetrieveAPIView
from django_ratelimit.decorators import ratelimit
from django_filters.rest_framework import DjangoFilterBackend
from .models import (ProfileImage, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest, StudyField, University, Transaction
)
from .serializers import (
    NewPasswordSerializer, PasswordResetRequestSerializer, ProfileImageSerializer, SecurityAnswerValidationSerializer, SecurityQuestionSerializer, SecurityAnswerSerializer, InterestSerializer, 
    ProfileSerializer, EWalletSerializer, DepositMethodSerializer, DepositRequestSerializer, AddInterestSerializer,RemoveInterestSerializer, StudyFieldSerializer, UniversitySerializer, TransactionSerializer
)
from rest_framework.permissions import AllowAny
from .permissions import IsStudent,IsReception, IsAdminOrReception, IsOwnerOrAdminOrReception
from django_ratelimit.exceptions import Ratelimited
from rest_framework.exceptions import NotFound
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.auth import get_user_model
import secrets
import logging
from django.db.models import Q
from decimal import Decimal
import time

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]

class SecurityQuestionViewSet(viewsets.ModelViewSet):
    queryset = SecurityQuestion.objects.all()
    serializer_class = SecurityQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['question_text']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrReception()]
        return [permissions.IsAuthenticated()]


class SecurityAnswerViewSet(viewsets.ModelViewSet):
    serializer_class = SecurityAnswerSerializer
    permission_classes = [IsOwnerOrAdminOrReception]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SecurityAnswer.objects.all()
        return SecurityAnswer.objects.filter(user=user)


class InterestViewSet(viewsets.ModelViewSet):
    queryset = Interest.objects.all()
    serializer_class = InterestSerializer
    permission_classes = [permissions.IsAuthenticated,IsStudent]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'category']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsStudent()]
        return [permissions.IsAuthenticated()]

class UniversityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = University.objects.all()
    serializer_class = UniversitySerializer

class StudyFieldViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StudyField.objects.all()
    serializer_class = StudyFieldSerializer

class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name']
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list']:
            # For listing profiles, only admin/reception can view all
            permission_classes = [permissions.IsAuthenticated, IsAdminOrReception]
        elif self.action in ['retrieve']:
            # For single profile view, allow owner or admin/reception
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdminOrReception]
        else:
            # For create/update/delete, use default permissions
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        base_qs = Profile.objects.select_related(
            'user', 'university', 'studyfield'
        ).prefetch_related(
            'profileinterest_set__interest',
            'image'
        )

        if user.is_staff or user.user_type in ['admin', 'reception']:
            return base_qs
        return base_qs.filter(user=user)
    
    def get_serializer_class(self):
        if self.action in ['retrieve']:
            return ProfileSerializer
        elif self.action == 'add_interest':
            return AddInterestSerializer
        elif self.action == 'remove_interest':
            return RemoveInterestSerializer
        return ProfileSerializer

    @action(detail=True, methods=['post'])
    def add_interest(self, request, pk=None):
        profile = self.get_object()
        serializer = AddInterestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        interest_id = serializer.validated_data['interest']
        intensity = serializer.validated_data['intensity']
        
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
        serializer = RemoveInterestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        interest_id = serializer.validated_data['interest']
        
        try:
            profile_interest = ProfileInterest.objects.get(profile=profile, interest_id=interest_id)
            profile_interest.delete()
            return Response({'status': 'interest removed'}, status=status.HTTP_200_OK)
        except ProfileInterest.DoesNotExist:
            return Response({'error': 'Interest not found for this profile'}, status=status.HTTP_404_NOT_FOUND)

class UserProfileView(RetrieveAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Profile.objects.select_related(
            'user', 'university', 'studyfield'
        ).prefetch_related(
            'profileinterest_set__interest',
            'image'
        )

    def get_object(self):
        try:
            return self.get_queryset().get(user=self.request.user)
        except Profile.DoesNotExist:
            raise NotFound("Profile not found")

class ProfileImageViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ProfileImage.objects.filter(profile__user=user)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        serializer.save(profile=profile)
    
    def create(self, request, *args, **kwargs):
        profile = request.user.profile
        if hasattr(profile, 'image'):
            return Response(
                {"error": "Profile image already exists. Use PUT to update."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'status']
    search_fields = ['reference_id', 'description']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type == 'reception':
            return Transaction.objects.all().select_related('sender', 'receiver')
        return Transaction.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver')

class EWalletViewSet(viewsets.ModelViewSet):
    serializer_class = EWalletSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type == 'reception':
            return EWallet.objects.all().select_related('owner')
        return EWallet.objects.filter(owner=user).select_related('owner')
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        wallet = self.get_object()
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
        
        try:
            # Create deposit request
            deposit_request = DepositRequest.objects.create(
                wallet=wallet,
                amount=amount,
                status='pending'
            )
            
            # Create transaction record
            Transaction.objects.create(
                sender=None,  # External deposit
                receiver=wallet.owner,
                amount=amount,
                transaction_type='deposit',
                status='pending',
                description=f"Deposit request for wallet {wallet.id}",
                reference_id=f"DEP-{deposit_request.id}"
            )
            
            return Response({
                'message': 'Deposit request created successfully',
                'deposit_request_id': deposit_request.id
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        wallet = self.get_object()
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
        
        if amount <= 0:
            return Response(
                {'error': 'Withdrawal amount must be positive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount > wallet.balance:
            return Response(
                {'error': 'Insufficient balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Process withdrawal
            wallet.balance -= amount
            wallet.save()
            
            # Create transaction record
            Transaction.objects.create(
                sender=wallet.owner,
                receiver=None,  # External withdrawal
                amount=amount,
                transaction_type='withdrawal',
                status='completed',
                description=f"Withdrawal from wallet {wallet.id}",
                reference_id=f"WTH-{int(time.time())}"
            )
            
            return Response({
                'message': 'Withdrawal successful',
                'new_balance': wallet.balance
            })
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class DepositMethodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepositMethod.objects.filter(is_active=True)
    serializer_class = DepositMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
class DepositRequestViewSet(viewsets.ModelViewSet):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = DepositRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if IsAdminOrReception().has_permission(self.request, self):
            return DepositRequest.objects.all()
        return DepositRequest.objects.filter(user=user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'screenshot_path': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Upload receipt screenshot (JPG/PNG, max 5MB)'
                    },
                    'deposit_method': {'type': 'integer', 'description': 'Deposit method ID'},
                    'transaction_number': {'type': 'string', 'description': 'Transaction reference'},
                    'amount': {'type': 'number', 'description': 'Deposit amount'}
                },
                'required': ['screenshot_path', 'deposit_method', 'transaction_number', 'amount']
            }
        },
        description="Create a new deposit request with receipt upload"
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        if 'screenshot_path' not in request.FILES:
            return Response({'error': 'screenshot_path is required'}, status=status.HTTP_400_BAD_REQUEST)

        screenshot_file = request.FILES['screenshot_path']

        if screenshot_file.size > 5 * 1024 * 1024:
            return Response({'error': 'File too large (max 5MB)'}, status=status.HTTP_400_BAD_REQUEST)

        if not screenshot_file.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            return Response({'error': 'Only JPG/PNG files allowed'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            deposit_request = DepositRequest.objects.create(
                user=request.user,
                deposit_method_id=request.data.get('deposit_method'),
                transaction_number=request.data.get('transaction_number'),
                amount=request.data.get('amount'),
                screenshot_path=screenshot_file,
                status='pending'
            )
            serializer = self.get_serializer(deposit_request)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Failed to create deposit request: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrReception])
    def approve(self, request, pk=None):
        deposit_request = self.get_object()
        try:
            deposit_request.approve()
            return Response({'status': 'deposit approved'})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrReception])
    def reject(self, request, pk=None):
        deposit_request = self.get_object()
        try:
            deposit_request.reject()
            return Response({'status': 'deposit rejected'})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetViewSet(viewsets.ViewSet):
    """
    Password reset flow using phone number and security questions
    """
    authentication_classes = []  # Disables authentication
    permission_classes = [AllowAny]  # Allows unauthenticated access

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="User's security questions",
                response=SecurityQuestionSerializer(many=True)
            ),
            400: OpenApiResponse(
                description="Invalid phone number",
                examples=[
                    OpenApiExample(
                        "Error Example",
                        value={"error": "User not found"}
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Request Example",
                value={"phone": "1234567890"},
                request_only=True
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def request_reset(self, request):
        """
        Step 1: Request password reset and get security questions
        """
        def _handle_request(request):
            serializer = PasswordResetRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            try:
                phone = serializer.validated_data['phone']
                user = User.objects.get(phone=phone)
                questions = SecurityQuestion.objects.filter(
                    securityanswer__user=user
                ).distinct()
                
                logger.info(f"Password reset requested for phone: {phone}")
                
                return Response({
                    'questions': SecurityQuestionSerializer(questions, many=True).data
                })
            except User.DoesNotExist:
                logger.warning(f"Password reset attempted for non-existent phone: {serializer.validated_data.get('phone', 'unknown')}")
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Error in password reset request: {str(e)}")
                return Response(
                    {'error': 'An error occurred processing your request'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Apply rate limiting
        try:
            request_func = ratelimit(key='ip', rate='5/h')(_handle_request)
            return request_func(request)
        except Ratelimited:
            logger.warning(f"Rate limit exceeded for IP: {request.META.get('REMOTE_ADDR', 'unknown')}")
            return Response(
                {'error': 'Too many attempts. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    @extend_schema(
        request=SecurityAnswerValidationSerializer,
        responses={
            200: OpenApiResponse(
                description="Temporary reset token",
                examples=[
                    OpenApiExample(
                        "Success Example",
                        value={"reset_token": "abc123xyz456"}
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Wrong answer or invalid data"
            )
        },
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "phone": "1234567890",
                    "question_id": 1,
                    "answer": "My security answer"
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def validate_answers(self, request):
        """
        Step 2: Validate security answers and generate reset token
        """
        def _handle_validation(request):
            serializer = SecurityAnswerValidationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            try:
                user = User.objects.get(phone=serializer.validated_data['phone'])
                
                # Generate secure token
                reset_token = secrets.token_urlsafe(32)
                
                # Store token with expiration
                user.reset_token = reset_token
                user.reset_token_expires = timezone.now() + timezone.timedelta(hours=1)
                user.save()
                
                logger.info(f"Security answer validated for user ID: {user.id}")
                
                return Response({'reset_token': reset_token})
            except User.DoesNotExist:
                logger.warning(f"Security answer validation attempted for non-existent phone: {serializer.validated_data.get('phone', 'unknown')}")
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Error in security answer validation: {str(e)}")
                return Response(
                    {'error': 'An error occurred processing your request'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Apply rate limiting
        try:
            validation_func = ratelimit(key='ip', rate='5/h')(_handle_validation)
            return validation_func(request)
        except Ratelimited:
            logger.warning(f"Rate limit exceeded for IP: {request.META.get('REMOTE_ADDR', 'unknown')}")
            return Response(
                {'error': 'Too many attempts. Please try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    @extend_schema(
        request=NewPasswordSerializer,
        responses={
            200: OpenApiResponse(
                description="Password changed successfully",
                examples=[
                    OpenApiExample(
                        "Success Example",
                        value={"status": "Password reset successful"}
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid token or weak password"
            )
        },
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                    "reset_token": "abc123xyz456",
                    "new_password": "NewSecurePassword123!",
                    "confirm_password": "NewSecurePassword123!"
                }
            )
        ]
    )
    @action(detail=False, methods=['post'])
    def confirm_reset(self, request):
        """
        Step 3: Set new password after validation
        """
        serializer = NewPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            reset_token = serializer.validated_data['reset_token']
            user = User.objects.get(reset_token=reset_token)
            
            # Check if token has expired
            if not user.reset_token_expires or user.reset_token_expires < timezone.now():
                logger.warning(f"Expired reset token used for user ID: {user.id}")
                return Response(
                    {'error': 'Token has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Password validation was already handled in serializer
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            
            # Clear the reset token
            user.reset_token = None
            user.reset_token_expires = None
            user.save()
            
            # Log the successful password reset
            logger.info(f"Password reset successful for user ID: {user.id}")
            
            # Invalidate all existing sessions (optional)
            try:
                from django.contrib.sessions.models import Session
                user_sessions = Session.objects.filter(session_data__contains=str(user.id))
                for session in user_sessions:
                    session.delete()
            except Exception as e:
                logger.warning(f"Failed to invalidate sessions: {str(e)}")
            
            return Response({'status': 'Password reset successful'})
            
        except User.DoesNotExist:
            logger.warning(f"Invalid reset token used: {serializer.validated_data.get('reset_token', 'unknown')}")
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in password reset confirmation: {str(e)}")
            return Response(
                {'error': 'An error occurred processing your request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )