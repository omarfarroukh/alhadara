from rest_framework import serializers
from .models import ReferralCode, ReferralUsage

class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCode
        fields = ['id', 'user', 'code', 'created_at']
        read_only_fields = ['user', 'created_at']

class ReferralUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralUsage
        fields = ['id', 'code', 'used_by', 'used_at']
        read_only_fields = ['used_at'] 