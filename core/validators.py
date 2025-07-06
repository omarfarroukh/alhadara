from django.core.validators import RegexValidator
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import re

syrian_phone_validator = RegexValidator(
    regex=r'^(09\d{8}|\+9639\d{8}|009639\d{8})$',  # Note the 9 after 00963
    message="Phone number must be: 09XXXXXXXX, +9639XXXXXXXX, or 009639XXXXXXXX"
)

def validate_password_strength(value):
    """
    Validate password meets strong requirements (consistent across all serializers)
    """
    try:
        # Use Django's built-in password validation
        validate_password(value)
    except ValidationError as e:
        raise serializers.ValidationError(list(e.messages))

    # Additional custom validation
    if len(value) < 8:  # Consistent length requirement
        raise serializers.ValidationError("Password must be at least 12 characters long")
    
    if not re.search(r'[A-Z]', value):
        raise serializers.ValidationError("Password must contain at least one uppercase letter")
        
    if not re.search(r'[a-z]', value):
        raise serializers.ValidationError("Password must contain at least one lowercase letter")
        
    if not re.search(r'[0-9]', value):
        raise serializers.ValidationError("Password must contain at least one digit")
        
    if not re.search(r'[^A-Za-z0-9]', value):
        raise serializers.ValidationError("Password must contain at least one special character")

    return value
