from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action,api_view,permission_classes,authentication_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rq.job import Job
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from django_rq import get_queue
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema,OpenApiExample, OpenApiResponse,inline_serializer,OpenApiParameter
from django.utils.crypto import get_random_string
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from core.signals import push_counter_sync
from core.utils import generate_captcha, validate_captcha
from .throttles import LoginRateThrottle
from drf_spectacular.types import OpenApiTypes
from rest_framework.generics import RetrieveAPIView
from django_ratelimit.decorators import ratelimit
from django_filters.rest_framework import DjangoFilterBackend
from .models import (ProfileImage, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest, StudyField, University, Transaction, Notification, WithdrawalRequest
)
from .serializers import (
    NewPasswordSerializer, PasswordResetRequestSerializer, ProfileImageSerializer, SecurityAnswerValidationSerializer, SecurityQuestionSerializer, SecurityAnswerSerializer, InterestSerializer, 
    ProfileSerializer, EWalletSerializer, DepositMethodSerializer, DepositRequestSerializer, AddInterestSerializer,RemoveInterestSerializer, StudyFieldSerializer, TeacherSerializer, UniversitySerializer, TransactionSerializer, NotificationSerializer,
    PasswordResetOTPRequestSerializer, PasswordResetOTPValidateSerializer, WithdrawalRequestSerializer
)
from django.conf import settings
from rest_framework.permissions import AllowAny
from .permissions import IsReceptionOrStudent, IsStudent,IsReception, IsAdminOrReception, IsOwnerOrAdminOrReception
from django_ratelimit.exceptions import Ratelimited
from rest_framework.exceptions import NotFound
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.auth import get_user_model
import secrets
import logging
from django.core.cache import cache
import uuid
from django.db.models import Q
from decimal import Decimal
import time
from .tasks import  notify_deposit_request_created_task,notify_deposit_status_changed_task, notify_ewallet_withdrawal_task, notify_password_changed_task, send_telegram_password_reset_otp_task
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
User = get_user_model()

@api_view(['GET'])
@permission_classes([AllowAny])
def get_captcha(request):
    key, img = generate_captcha()
    return Response({'key': key, 'image': img})

@extend_schema(
    summary="Validate a CAPTCHA answer",
    description=(
        "Send the **captcha_key** you received from `GET /api/captcha/` "
        "together with the **answer** the user typed.  \n"
        "The key can only be used **once** and expires after **5 minutes**."
    ),
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "key":    {"type": "string", "description": "CAPTCHA key"},
                "answer": {"type": "string", "description": "6-character answer"},
            },
            "required": ["key", "answer"],
            "example": {"key": "aBc123", "answer": "H7K9M2"},
        }
    },
    responses={
        200: {"description": "Answer is correct", "example": {"valid": True}},
        400: {"description": "Answer is wrong or key expired", "example": {"valid": False}},
    },
    examples=[
        OpenApiExample(
            "Valid request",
            value={"key": "aBc123", "answer": "H7K9M2"},
            request_only=True,
        ),
        OpenApiExample(
            "Valid response",
            value={"valid": True},
            response_only=True,
        ),
    ],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_captcha(request):
    key    = request.data.get('key')
    answer = request.data.get('answer')
    ok     = validate_captcha(key, str(answer))
    return Response({'valid': ok}, status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST)




class TeacherViewSet(viewsets.ViewSet):
    """
    API endpoint that allows teachers to be viewed.
    Only accessible by admin and reception users.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(user_type='teacher').order_by('last_name', 'first_name')

    @extend_schema(
        responses={200: TeacherSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name='is_active',
                type=bool,
                required=False,
                description='Filter by active status (true/false)'
            ),
        ]
    )
    def list(self, request):
        # Check if user has permission
        if not (request.user.user_type in ['admin', 'reception'] or request.user.is_staff):
            return Response(
                {"detail": "You do not have permission to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = self.get_queryset()
        
        # Optional filtering by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)

        serializer = TeacherSerializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema(
    request=inline_serializer(
        name="StartVerificationRequest",
        fields={
            "phone": serializers.CharField(
                help_text="User's phone number (e.g., +9639XXXXXXXX)"
            )
        },
    ),
    responses={
        200: inline_serializer(
            name="StartVerificationResponse",
            fields={
                "deep_link": serializers.CharField(
                    help_text="Telegram deep link for verification"
                )
            },
        ),
        400: OpenApiResponse(description="Invalid phone number or unauthorized request"),
        403: OpenApiResponse(description="Phone number doesn't match JWT token"),
    },
    examples=[
        OpenApiExample(
            "Example request",
            value={"phone": "+963987654321"},
            request_only=True,
        ),
        OpenApiExample(
            "Example response",
            value={"deep_link": "https://t.me/YourBot?start=a1b2c3d4"},
            response_only=True,
        ),
    ],
    description="Initiate phone verification by generating a Telegram deep link. Only the phone number associated with the JWT token can request verification.",
)
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def start_verification(request):
    # Get phone from request
    requested_phone = request.data.get('phone')
    if not requested_phone:
        return Response({"error": "Phone number is required"}, status=400)
    
    # Get phone from JWT token
    jwt_phone = request.user.phone  # Assuming the phone is stored in the user model
    
    # Verify the requested phone matches the JWT phone
    if requested_phone != jwt_phone:
        return Response({"error": "You can only verify your own phone number"}, status=403)
    
    token = str(uuid.uuid4())
    cache.set(f"user_verification:{token}", requested_phone, timeout=300)  # 5-minute expiry
    
    deep_link = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"
    return Response({
        "token": token,
        "deep_link": deep_link
    })
    
# Schema for verify_pin
@extend_schema(
    request=inline_serializer(
        name="VerifyPinRequest",
        fields={
            "token": serializers.CharField(help_text="Token from the deep link"),
            "pin": serializers.CharField(help_text="6-digit PIN from Telegram"),
        },
    ),
    responses={
        200: inline_serializer(
            name="VerifyPinResponse",
            fields={
                "status": serializers.CharField(
                    help_text="Verification status"
                )
            },
        ),
        400: OpenApiResponse(description="Invalid PIN or expired token"),
    },
    examples=[
        OpenApiExample(
            "Example request",
            value={"token": "a1b2c3d4", "pin": "123456"},
            request_only=True,
        ),
        OpenApiExample(
            "Example response",
            value={"status": "verified"},
            response_only=True,
        ),
    ],
    description="Submit the PIN received via Telegram to verify the phone number",
)
@api_view(['POST'])
def verify_pin(request):
    token = request.data.get('token')
    pin = request.data.get('pin')
    
    if not token or not pin:
        return Response({"error": "Token and PIN are required"}, status=400)
    
    cached_pin = cache.get(f"verification_pin:{token}")
    if cached_pin == pin:
        phone = cache.get(f"user_verification:{token}")
        if not phone:
            return Response({"error": "Expired token"}, status=400)
            
        user = User.objects.get(phone=phone)
        user.is_verified = True
        user.save()
        return Response({"status": "verified"})
    
    return Response({"error": "Invalid PIN"}, status=400)


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

class EWalletViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EWalletSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type in ['admin', 'reception']:
            return EWallet.objects.filter(user__user_type='student').select_related('user')
        return EWallet.objects.filter(user=user).select_related('user')
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrReception])
    def admin_wallet(self, request):
        """Get admin wallet details - only accessible by admin and reception"""
        try:
            admin_user = User.objects.get(user_type='admin')
            admin_wallet = EWallet.objects.get(user=admin_user)
            serializer = self.get_serializer(admin_wallet)
            return Response(serializer.data)
        except (User.DoesNotExist, EWallet.DoesNotExist):
            return Response(
                {'error': 'Admin wallet not found'},
                status=status.HTTP_404_NOT_FOUND
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
                {'error': 'Invalid amount format'},
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
                sender=wallet.user,
                receiver=None,  # External withdrawal
                amount=amount,
                transaction_type='withdrawal',
                status='completed',
                description=f"Withdrawal from wallet {wallet.id}",
                reference_id=f"WTH-{int(time.time())}"
            )
            
            # Send notification
            notify_ewallet_withdrawal_task.delay(wallet.user.id, amount)
            
            return Response({
                'message': 'Withdrawal successful',
                'new_balance': wallet.balance
            })
            
        except Exception as e:
            return Response(
                {'error': 'Failed to process withdrawal. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class DepositMethodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DepositMethod.objects.filter(is_active=True)
    serializer_class = DepositMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'is_read']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    
    @extend_schema(
        summary="Mark one notification as read",
        request=None,
        responses={
            200: OpenApiResponse(
                description="Notification marked as read",
                examples={"application/json": {"status": "marked as read"}},
            )
        },
    )
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})
    
    @extend_schema(
        summary="Mark all notifications as read",
        request=None,
        responses={
            200: OpenApiResponse(
                description="All notifications marked as read",
                examples={"application/json": {"status": "all marked as read"}},
            )
        },
    )
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        user_id = request.user.id
        affected = qs.update(is_read=True)
        if affected:
            push_counter_sync(user_id)       
        return Response({'status': 'all marked as read'})
    
    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})

class DepositRequestViewSet(viewsets.ModelViewSet):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = DepositRequestSerializer
    permission_classes = [IsReceptionOrStudent]
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

        # Use the serializer to create the object
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            deposit_request = serializer.save()
            
            # Create PENDING transaction record
            Transaction.objects.create(
                sender=None,  # External deposit
                receiver=request.user,
                amount=deposit_request.amount,
                transaction_type='deposit',
                status='pending',
                description=f"Deposit request #{deposit_request.id}",
                reference_id=f"DEP-{deposit_request.id}"
            )
            
            # Send notification to reception and admin
            notify_deposit_request_created_task.delay(deposit_request.id)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrReception])
    def approve(self, request, pk=None):
        deposit_request = self.get_object()
        
        try:
            with transaction.atomic():  # Ensure all operations succeed or fail together
                # Approve the deposit request
                deposit_request.approve()
                
                # Update the associated transaction
                try:
                    transaction_obj = Transaction.objects.get(
                        reference_id=f"DEP-{deposit_request.id}"
                    )
                    transaction_obj.status = 'completed'
                    transaction_obj.save()
                except Transaction.DoesNotExist:
                    # Create transaction if it doesn't exist (fallback)
                    Transaction.objects.create(
                        sender=None,
                        receiver=deposit_request.user,
                        amount=deposit_request.amount,
                        transaction_type='deposit',
                        status='completed',
                        description=f"Deposit request #{deposit_request.id} (approved)",
                        reference_id=f"DEP-{deposit_request.id}"
                    )
                
                # Send notification
                notify_deposit_status_changed_task.delay(deposit_request.id, 'verified')
                
                return Response(
                    {'status': 'deposit approved', 'new_balance': str(deposit_request.user.wallet.current_balance)},
                    status=status.HTTP_200_OK
                )
                
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Approval failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrReception])
    def reject(self, request, pk=None):
        deposit_request = self.get_object()
        
        try:
            with transaction.atomic():
                # Reject the deposit request
                deposit_request.reject()
                
                # Update the associated transaction
                try:
                    transaction_obj = Transaction.objects.get(
                        reference_id=f"DEP-{deposit_request.id}"
                    )
                    transaction_obj.status = 'failed'
                    transaction_obj.save()
                except Transaction.DoesNotExist:
                    # Create transaction if it doesn't exist (fallback)
                    Transaction.objects.create(
                        sender=None,
                        receiver=deposit_request.user,
                        amount=deposit_request.amount,
                        transaction_type='deposit',
                        status='failed',
                        description=f"Deposit request #{deposit_request.id} (rejected)",
                        reference_id=f"DEP-{deposit_request.id}"
                    )
                
                # Send notification
                notify_deposit_status_changed_task.delay(deposit_request.id, 'rejected')
                
                return Response(
                    {'status': 'deposit rejected'},
                    status=status.HTTP_200_OK
                )
                
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Rejection failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
            
            # Send notification
            notify_password_changed_task.delay(user.id)

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

    @extend_schema(
        request=PasswordResetOTPRequestSerializer,
        responses={
            200: OpenApiResponse(description="OTP sent successfully."),
            400: OpenApiResponse(description="Invalid request or user does not have a linked Telegram account.")
        },
        description="Request a password reset OTP to be sent via Telegram."
    )
    @action(detail=False, methods=['post'], url_path='request-otp')
    def request_otp(self, request):
        serializer = PasswordResetOTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(phone=serializer.validated_data['phone'])
            otp = get_random_string(6, '0123456789')
            cache.set(f'password_reset_otp_{user.id}', otp, timeout=600)
            send_telegram_password_reset_otp_task.delay(user.id, otp)
            return Response({'status': 'OTP sent to your Telegram account.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=PasswordResetOTPValidateSerializer,
        responses={
            200: OpenApiResponse(description="OTP validated successfully, reset token returned."),
            400: OpenApiResponse(description="Invalid OTP or user not found.")
        },
        description="Validate the password reset OTP and get a reset token."
    )
    @action(detail=False, methods=['post'], url_path='validate-otp')
    def validate_otp(self, request):
        serializer = PasswordResetOTPValidateSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(phone=serializer.validated_data['phone'])
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expires = timezone.now() + timezone.timedelta(minutes=10)
            user.save()
            cache.delete(f'password_reset_otp_{user.id}')
            return Response({'reset_token': reset_token})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=NewPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password has been reset successfully."),
            400: OpenApiResponse(description="Invalid token, expired token, or passwords do not match.")
        },
        description="Confirm the password reset by providing the reset token and the new password."
    )
    @action(detail=False, methods=['post'], url_path='confirm-reset-with-token')
    def confirm_reset_with_token(self, request):
        serializer = NewPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(reset_token=serializer.validated_data['reset_token'])
                if user.reset_token_expires < timezone.now():
                    return Response({'error': 'Token has expired.'}, status=status.HTTP_400_BAD_REQUEST)
                user.set_password(serializer.validated_data['new_password'])
                user.reset_token = None
                user.reset_token_expires = None
                user.save()
                notify_password_changed_task.delay(user.id)
                return Response({'status': 'Password has been reset successfully.'})
            except User.DoesNotExist:
                return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
class JobStatusView(APIView):
    def get(self, request, job_id):
        job = Job.fetch(str(job_id), connection=get_queue().connection)  # <-- cast to str
        if job.is_finished:
            return Response({"status": "finished", "result": job.result})
        if job.is_failed:
            return Response({"status": "failed", "error": str(job.exc_info)})
        return Response({"status": "queued"})


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        'status': ['exact'],
        'requested_at': ['gte', 'lte'],
        'pickup_datetime': ['gte', 'lte'],
        'amount': ['gte', 'lte'],
    }
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
    ]
    ordering_fields = ['requested_at', 'amount', 'pickup_datetime']
    ordering = ['-requested_at']

    def get_queryset(self):
        user = self.request.user
        if user.user_type in ('reception', 'admin'):
            return WithdrawalRequest.objects.select_related('user')
        return WithdrawalRequest.objects.filter(user=user)

    # ---------------------------------
    # Reception-only custom endpoints
    # ---------------------------------
    @extend_schema(
        request=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(
                name='pickup_datetime',
                type=OpenApiTypes.DATETIME,
                description='ISO-8601 date-time when student will pick up cash',
                required=True,
            )
        ],
        responses={200: {'type': 'object', 'properties': {'status': {'type': 'string'}}}}
    )
    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminOrReception])
    def schedule(self, request, pk=None):
        wr = self.get_object()
        pickup = request.data.get('pickup_datetime')
        if not pickup:
            return Response({'pickup_datetime': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        wr.pickup_datetime = pickup
        wr.status = 'scheduled'
        wr.save(update_fields=['pickup_datetime', 'status'])
        return Response({'status': 'scheduled'})

    @extend_schema(
        request=None,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string'},
                    'new_balance': {'type': 'string'}
                }
            }
        }
    )
    @action(detail=True, methods=['post'],
            permission_classes=[IsAdminOrReception])
    def complete(self, request, pk=None):
        wr = self.get_object()
        try:
            wr.mark_done(request.user)
        except ValidationError as e:
            return Response({'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'done',
                         'new_balance': str(wr.user.wallet.current_balance)})