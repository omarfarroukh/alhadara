from rest_framework import serializers
from django.contrib.auth.hashers import make_password, identify_hasher
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer, UserSerializer
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest
)


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    access = serializers.SerializerMethodField(read_only=True)
    refresh = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ('id', 'phone', 'password', 'first_name', 'middle_name', 
                'last_name', 'user_type', 'access', 'refresh')
        extra_kwargs = {
            'password': {'write_only': True},
            'first_name': {'required': True},
            'middle_name': {'required': True},
            'last_name': {'required': True},
        }

    def get_access(self, obj):
        refresh = RefreshToken.for_user(obj)
        return str(refresh.access_token)

    def get_refresh(self, obj):
        refresh = RefreshToken.for_user(obj)
        return str(refresh)
class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = User
        fields = ('id', 'phone', 'first_name', 'middle_name', 'last_name', 'user_type', 'is_active', 'last_login')
        extra_kwargs = {
            'phone': {
                'error_messages': {
                    'invalid': 'Please enter a valid Syrian phone number (09XXXXXXXX or +9639XXXXXXXX)'
                }
            }
        }
        
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['user_type'] = user.user_type
        return token
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
       
class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ('id', 'name', 'category')


class ProfileInterestSerializer(serializers.ModelSerializer):
    interest_name = serializers.ReadOnlyField(source='interest.name')
    interest_category = serializers.ReadOnlyField(source='interest.category')
    
    class Meta:
        model = ProfileInterest
        fields = ('interest', 'interest_name', 'interest_category', 'intensity')


class ProfileSerializer(serializers.ModelSerializer):
    interests = ProfileInterestSerializer(source='profileinterest_set', many=True, read_only=True)
    
    class Meta:
        model = Profile
        fields = (
            'id', 'birth_date', 'gender', 
            'national_id', 'address', 'interests'
        )


class ProfileDetailSerializer(ProfileSerializer):
    user = CustomUserSerializer(read_only=True)
    
    class Meta(ProfileSerializer.Meta):
        fields = ProfileSerializer.Meta.fields + ('user',)


class EWalletSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    
    class Meta:
        model = EWallet
        fields = ('id', 'user', 'user_username', 'current_balance', 'last_updated')
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


class DepositRequestSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    deposit_method_name = serializers.ReadOnlyField(source='deposit_method.get_name_display')
    
    class Meta:
        model = DepositRequest
        fields = (
            'id', 'user', 'user_username', 'deposit_method', 'deposit_method_name',
            'transaction_number', 'amount', 'screenshot_path', 'status', 'created_at',
            'wallet'
        )
        read_only_fields = ('user', 'status', 'created_at')
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)