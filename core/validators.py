from django.core.validators import RegexValidator

syrian_phone_validator = RegexValidator(
    regex=r'^(09\d{8}|\+9639\d{8}|009639\d{8})$',  # Note the 9 after 00963
    message="Phone number must be: 09XXXXXXXX, +9639XXXXXXXX, or 009639XXXXXXXX"
)