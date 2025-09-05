from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer, UserSerializer
from .models import ( ProfileImage, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest, StudyField, University, Transaction, Notification, FileStorage, WithdrawalRequest
)
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from .validators import validate_password_strength
from core.utils import TranslationMixin
User = get_user_model()

class CustomUserCreateSerializer(serializers.ModelSerializer):
    access = serializers.SerializerMethodField(read_only=True)
    refresh = serializers.SerializerMethodField(read_only=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    is_verified = serializers.BooleanField(read_only=True)  # Add this line

    captcha_key     = serializers.CharField(write_only=True, required=False)
    captcha_answer  = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ('id', 'phone', 'password', 'confirm_password', 'first_name', 
                'middle_name', 'last_name', 'user_type', 'access', 'refresh', 'is_verified', 'captcha_key', 'captcha_answer')
        extra_kwargs = {
            'password': {
                'write_only': True,
                'required': True,
                'style': {'input_type': 'password'}
            },
            'first_name': {'required': True},
            'middle_name': {'required': True},
            'last_name': {'required': True},
            'user_type': {'read_only': False}  # Ensure it can be written during creation
        }

    def validate_user_type(self, value):
        """Validate that user_type is one of the allowed choices"""
        if value not in dict(User.USER_TYPE_CHOICES).keys():
            raise serializers.ValidationError("Invalid user type")
        return value

    def validate_password(self, value):
        """Validate password meets strong requirements"""
        return validate_password_strength(value)
    
    def validate(self, data):
        """Check that passwords match"""
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
          # Captcha only for students
        if data.get('user_type') == 'student':
            key    = data.pop('captcha_key', None)
            answer = data.pop('captcha_answer', None)
            if key is None or answer is None:
                raise serializers.ValidationError({'captcha_answer': 'CAPTCHA required for students'})
            from .utils import validate_captcha
            if not validate_captcha(key, answer):
                raise serializers.ValidationError({'captcha_answer': 'Invalid or expired CAPTCHA'})
        else:
            # Admin / reception / teacher – silently drop captcha fields
            data.pop('captcha_key', None)
            data.pop('captcha_answer', None)
        return data

    def create(self, validated_data):
        """Create user with validated data"""
        validated_data.pop('confirm_password')
        
        is_verified = validated_data.get('user_type') != 'student' #only students are set to false
        
        user = User.objects.create_user(
            phone=validated_data['phone'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            middle_name=validated_data['middle_name'],
            last_name=validated_data['last_name'],
            user_type=validated_data['user_type'],  # Now required (no default)
            is_verified=is_verified,  
        )
        return user

    def get_access(self, obj):
        refresh = RefreshToken.for_user(obj)
        return str(refresh.access_token)

    def get_refresh(self, obj):
        refresh = RefreshToken.for_user(obj)
        return str(refresh)

    def to_representation(self, instance):
        """Ensure consistent output format with user_type"""
        data = super().to_representation(instance)
        # Explicitly include user_type in the response
        data['user_type'] = instance.user_type
        return data
    
class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = User
        fields = ('id', 'phone', 'first_name', 'middle_name', 'last_name', 
                 'user_type', 'is_active','is_verified', 'last_login')
        extra_kwargs = {
            'phone': {
                'error_messages': {
                    'invalid': 'Please enter a valid Syrian phone number (09XXXXXXXX or +9639XXXXXXXX)'
                }
            }
        }
        
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        """Add user_type to the token response"""
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        
        data.update({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_type': self.user.user_type,
            'phone': self.user.phone,
            'is_verified':self.user.is_verified
        })
        return data

    @classmethod
    def get_token(cls, user):
        """Add user_type to the token claims"""
        token = super().get_token(user)
        token['user_type'] = user.user_type
        return token
    
class TeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'middle_name', 'last_name','full_name', 'phone', 'user_type', 'is_active']
        read_only_fields = fields
        
    def get_full_name(self, obj):
        return obj.get_full_name()    
    
class SecurityQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityQuestion
        fields = ('id', 'question_text', 'language')

class SecurityAnswerSerializer(serializers.ModelSerializer):
    # Add a write-only field for the plain text answer
    answer = serializers.CharField(write_only=True)
    
    class Meta:
        model = SecurityAnswer
        fields = ('id', 'user', 'question', 'answer_hash', 'answer')
        read_only_fields = ('user', 'answer_hash')  # answer_hash is now read-only
   
        
    def create(self, validated_data):
        # Get the plain text answer from input
        plain_answer = validated_data.pop('answer')
        
        # Hash the answer and store it
        validated_data['answer_hash'] = make_password(plain_answer)
        
        # Set the current user
        validated_data['user'] = self.context['request'].user
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'answer' in validated_data:
            plain_answer = validated_data.pop('answer')
            instance.answer_hash = make_password(plain_answer)
        return super().update(instance, validated_data)

class PasswordResetRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(
        required=True,
        help_text="Registered phone number",
        max_length=20,
        error_messages={
            "required": "Phone number is required",
            "max_length": "Phone number must not exceed 20 characters"
        }
    )

    def validate_phone(self, value):
        if not User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("No user registered with this number")
        return value
    
class SecurityAnswerValidationSerializer(serializers.Serializer):
    phone = serializers.CharField(
        required=True,
        help_text="Phone number used in first step"
    )
    question_id = serializers.IntegerField(
        required=True,
        help_text="ID of the selected security question",
        min_value=1,
        error_messages={
            "min_value": "Question ID must be a positive number"
        }
    )
    answer = serializers.CharField(
        required=True,
        help_text="User's answer to the security question",
        trim_whitespace=False
    )

    def validate(self, data):
        try:
            user = User.objects.get(phone=data['phone'])
            question = SecurityQuestion.objects.get(id=data['question_id'])
            security_answer = user.securityanswer_set.get(question=question)
            
            if not security_answer.check_answer(data['answer']):
                raise serializers.ValidationError(
                    {"answer": "Incorrect answer"}
                )
                
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"phone": "Phone number not registered"}
            )
        except SecurityQuestion.DoesNotExist:
            raise serializers.ValidationError(
                {"question_id": "Question not found"}
            )
        except:
            raise serializers.ValidationError(
                {"answer": "No matching security question found"}
            )
            
        return data
    
class NewPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField(
        required=True,
        help_text="Temporary token received from step 2",
        min_length=10,
        error_messages={
            "min_length": "Invalid token"
        }
    )
    new_password = serializers.CharField(
        required=True,
        help_text="New password",
        min_length=8,
        max_length=128,
        write_only=True,
        error_messages={
            "min_length": "Password must be at least 8 characters",
            "max_length": "Password must not exceed 128 characters"
        }
    )
    confirm_password = serializers.CharField(
        required=True,
        help_text="Confirm new password",
        min_length=8,
        max_length=128,
        write_only=True,
        error_messages={
            "min_length": "Password must be at least 8 characters",
            "max_length": "Password must not exceed 128 characters"
        }
    )

    def validate(self, data):
            if data['new_password'] != data['confirm_password']:
                raise serializers.ValidationError(
                    {"confirm_password": "Passwords do not match"}
                )
            try:
                validate_password_strength(data['new_password'])
            except serializers.ValidationError as e:
                raise serializers.ValidationError({"new_password": e.detail})
                
            return data        


class PasswordResetOTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        try:
            user = User.objects.get(phone=value)
            if not user.telegram_chat_id:
                raise serializers.ValidationError("This user does not have a connected Telegram account.")
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this phone number does not exist.")
        return value


class PasswordResetOTPValidateSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            user = User.objects.get(phone=data['phone'])
            cached_otp = cache.get(f'password_reset_otp_{user.id}')
            if not cached_otp or cached_otp != data['otp']:
                raise serializers.ValidationError("Invalid OTP.")
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return data


class UniversitySerializer(TranslationMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = University
        fields = ['id', 'name']
        
    def get_name(self, obj):
        return self.get_translated_field(obj.name)
    
class StudyFieldSerializer(TranslationMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyField
        fields = ['id', 'name']

    def get_name(self, obj):
        return self.get_translated_field(obj.name)

class InterestSerializer(TranslationMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    class Meta:
        model = Interest
        fields = ('id', 'name', 'category')
    
    def get_name(self, obj):
        return self.get_translated_field(obj.name)
        

class InterestCreateSerializer(TranslationMixin, serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ('id', 'name', 'category')

class AddInterestSerializer(serializers.Serializer):
    interest = serializers.IntegerField(help_text="ID of the interest to add")
    intensity = serializers.IntegerField(
        default=3, 
        min_value=1, 
        max_value=5,
        help_text="Intensity level from 1-5"
    )

class RemoveInterestSerializer(serializers.Serializer):
    interest = serializers.IntegerField(help_text="ID of the interest to remove")
    
class ProfileInterestSerializer(TranslationMixin, serializers.ModelSerializer):
    # The name is on the related interest object
    interest_name = serializers.SerializerMethodField()
    interest_category = serializers.ReadOnlyField(source='interest.category')
    
    class Meta:
        model = ProfileInterest
        fields = ('interest', 'interest_name', 'interest_category', 'intensity')

    def get_interest_name(self, obj):
        if obj.interest:
            return self.get_translated_field(obj.interest.name)
        return None



class ProfileImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileImage
        fields = ['id', 'image']
    
    def validate(self, attrs):
        try:
            # Run model's clean() method during validation
            instance = ProfileImage(**attrs)
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)  # Convert to DRF error
        return attrs
        

class ProfileSerializer(serializers.ModelSerializer):
    interests = ProfileInterestSerializer(source='profileinterest_set', many=True, read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    studyfield = serializers.PrimaryKeyRelatedField(queryset=StudyField.objects.all(), required=False, allow_null=True)
    university = serializers.PrimaryKeyRelatedField(queryset=University.objects.all(), required=False, allow_null=True)
    university_name = serializers.SerializerMethodField()
    studyfield_name = serializers.SerializerMethodField()
    academic_status = serializers.ChoiceField(choices=Profile.ACADEMIC_STATUS_CHOICES, required=False, allow_null=True)
    image = ProfileImageSerializer(many=False, read_only=True)
    
    # Language levels (read-only)
    english_level_display = serializers.SerializerMethodField()
    german_level_display = serializers.SerializerMethodField()
    french_level_display = serializers.SerializerMethodField()
    spanish_level_display = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            'id', 'birth_date', 'gender', 'address', 'academic_status','image',
            'university', 'studyfield', 'interests', 'full_name','university_name','studyfield_name',
            'english_level', 'english_level_display', 'german_level', 'german_level_display',
            'french_level', 'french_level_display', 'spanish_level', 'spanish_level_display'
        )
        read_only_fields = ['id', 'english_level', 'german_level', 'french_level', 'spanish_level']
        
    def get_university_name(self, obj):
        if obj.university:
            return self.get_translated_field(obj.university.name)
        return None # Return null if no university is linked

    def get_studyfield_name(self, obj):
        if obj.studyfield:
            return self.get_translated_field(obj.studyfield.name)
        return None # Return null if no study field is linked
    
    def create(self, validated_data):
        # Automatically set the user to the current user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
        
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message_dict)
        return instance
    
    def get_english_level_display(self, obj):
        if obj.english_level:
            return dict(obj.english_level.LEVEL_CHOICES)[obj.english_level.level]
        return None
    
    def get_german_level_display(self, obj):
        if obj.german_level:
            return dict(obj.german_level.LEVEL_CHOICES)[obj.german_level.level]
        return None
    
    def get_french_level_display(self, obj):
        if obj.french_level:
            return dict(obj.french_level.LEVEL_CHOICES)[obj.french_level.level]
        return None
    
    def get_spanish_level_display(self, obj):
        if obj.spanish_level:
            return dict(obj.spanish_level.LEVEL_CHOICES)[obj.spanish_level.level]
        return None

class EWalletSerializer(serializers.ModelSerializer):
    user_full_name = serializers.ReadOnlyField(source='user.get_full_name')
    user_phone = serializers.ReadOnlyField(source='user.phone')
    
    class Meta:
        model = EWallet
        fields = ('id', 'user', 'user_full_name', 'user_phone', 'current_balance', 'last_updated')
        read_only_fields = ('user', 'current_balance', 'last_updated')

class BankTransferInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransferInfo
        fields = ('id', 'deposit_method', 'account_name', 'account_number', 'bank_name', 'iban')

class MoneyTransferInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoneyTransferInfo
        fields = ('id', 'deposit_method', 'company_name', 'receiver_name', 'receiver_phone')

class DepositMethodSerializer(serializers.ModelSerializer):
    bank_info = BankTransferInfoSerializer(many=True, read_only=True)
    transfer_info = MoneyTransferInfoSerializer(many=True, read_only=True)
    
    class Meta:
        model = DepositMethod
        fields = ('id', 'name', 'is_active', 'bank_info', 'transfer_info')
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.name == 'bank_transfer':
            representation.pop('transfer_info')
        elif instance.name == 'money_transfer':
            representation.pop('bank_info')
        return representation

class DepositRequestSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    deposit_method_name = serializers.CharField(source='deposit_method.name', read_only=True)
    screenshot_url = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = DepositRequest
        fields = [
            'id', 'user', 'user_phone', 'deposit_method', 'deposit_method_name',
            'transaction_number', 'amount', 'screenshot_path', 'screenshot_url',
            'status', 'created_at'
        ]
        read_only_fields = ['user', 'status', 'created_at']
    
    def get_screenshot_url(self, obj):
        request = self.context.get('request')
        if obj.screenshot_path and hasattr(obj.screenshot_path, 'url'):
            return request.build_absolute_uri(obj.screenshot_path.url)
        return None

    def validate_screenshot_path(self, value):
        if not value:
            raise serializers.ValidationError("No file was submitted.")
        
        # Check file size
        if hasattr(value, 'size') and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File too large (max 5MB)")
        
        # Check file extension
        if hasattr(value, 'name') and not value.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise serializers.ValidationError("Only JPG/PNG files allowed")
        
        return value
    
    def create(self, validated_data):
        # Debug print
        print("DEBUG validated_data:", validated_data)
        # Remove 'user' if present in validated_data
        validated_data.pop('user', None)
        # Set the user from the request context
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
            validated_data['status'] = 'pending'
        else:
            raise serializers.ValidationError("Authentication required")
        # Create the instance - Django will handle the file upload automatically
        return DepositRequest.objects.create(**validated_data)

class TransactionSerializer(TranslationMixin, serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    # Add translation for description
    description = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = (
            'id', 'reference_id', 'transaction_type', 'amount',
            'sender', 'sender_name', 'receiver', 'receiver_name',
            'status', 'description', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'reference_id')
    
    def get_description(self, obj):
        return self.get_translated_field(obj.description)

    def get_sender_name(self, obj):
        # Usernames should not be translated
        if obj.sender:
            return obj.sender.get_full_name()
        return None
    
    def get_receiver_name(self, obj):
        if obj.receiver:
            return obj.receiver.get_full_name()
        return None
    
class NotificationSerializer(TranslationMixin, serializers.ModelSerializer):
    # Add translations for title and message
    title = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ('id', 'notification_type', 'title', 'message', 'data', 'is_read', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_title(self, obj):
        return self.get_translated_field(obj.title)

    def get_message(self, obj):
        return self.get_translated_field(obj.message)
        
class TelegramFileSerializer(serializers.Serializer):
    """Serializes Telegram file metadata for API responses."""
    file_id = serializers.CharField()
    download_link = serializers.URLField()

class FileStorageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileStorage
        fields = ['id', 'telegram_file_id', 'telegram_download_link', 'file', 'uploaded_at']
        read_only_fields = fields

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WithdrawalRequest
        fields = ['id', 'amount', 'requested_at', 'pickup_datetime',
                  'status', 'handled_at']
        read_only_fields = ['id', 'requested_at', 'status', 'handled_at']

    def validate_amount(self, value):
        user = self.context['request'].user
        if user.wallet.current_balance < value:
            raise serializers.ValidationError("Insufficient balance.")
        return value

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)