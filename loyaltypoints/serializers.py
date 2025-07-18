from rest_framework import serializers
from .models import LoyaltyPoint
from core.models import Transaction

class LoyaltyPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyPoint
        fields = ['id', 'student', 'points', 'updated_at']
        read_only_fields = ['student', 'updated_at']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__' 
        
class LoyaltyConvertRequestSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=1,
        help_text="Number of loyalty points to convert to e-wallet balance."
    )