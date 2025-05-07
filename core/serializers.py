from rest_framework import serializers
from djoser.serializers import UserCreateSerializer, UserSerializer
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest
)


class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'username', 'email', 'password', 'phone', 'user_type')


class CustomUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        model = User
        fields = ('id', 'username', 'email', 'phone', 'user_type', 'is_active', 'last_login')


class SecurityQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityQuestion
        fields = ('id', 'question_text', 'language')


class SecurityAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAnswer
        fields = ('id', 'user', 'question', 'answer_hash')
        read_only_fields = ('user',)

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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
            'id', 'full_name', 'birth_date', 'gender', 
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