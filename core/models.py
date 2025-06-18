from decimal import Decimal
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .validators import syrian_phone_validator
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.contrib.auth.hashers import make_password, is_password_usable
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver


class CustomUserManager(BaseUserManager):
    def create_user(self, phone, first_name, middle_name, last_name, password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        if not first_name:
            raise ValueError('First name is required')
        if not middle_name:  # New validation
            raise ValueError('Middle name is required')
        if not last_name:
            raise ValueError('Last name is required')
        
        user = self.model(
            phone=phone,
            first_name=first_name,
            middle_name=middle_name,  # Now required
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone, first_name, middle_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        
        return self.create_user(phone, first_name, middle_name, last_name, password, **extra_fields)
    
class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('reception', 'Reception'),
        ('admin', 'Admin')
    )
    
    # Personal Info
    first_name = models.CharField(max_length=150)  # Removed blank/null
    middle_name = models.CharField(max_length=150)  # Removed blank/null, now required
    last_name = models.CharField(max_length=150)  # Removed blank/null
    
    # Authentication Info
    phone = models.CharField(
        max_length=20,
        unique=True,
        validators=[syrian_phone_validator]
    )
    
    # Role and Permissions
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Timestamps
    last_login = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    # Password reset fields
    reset_token = models.CharField(max_length=100, null=True, blank=True, unique=True)
    reset_token_expires = models.DateTimeField(null=True, blank=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['first_name', 'middle_name', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"
    
    def get_full_name(self):
        names = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(filter(None, names)).strip()
    
    def get_short_name(self):
        return self.first_name

@receiver(pre_save, sender=User)
def ensure_single_admin(sender, instance, **kwargs):
    """Ensure only one admin user exists in the system"""
    if instance.is_superuser:
        # Check if there's another superuser
        other_admin = User.objects.filter(
            is_superuser=True
        ).exclude(pk=instance.pk).first()
        
        if other_admin:
            raise ValidationError(
                "Only one admin user is allowed in the system."
            )

class SecurityQuestion(models.Model):
    LANGUAGE_CHOICES = (
        ('ar', 'Arabic'),
        ('en', 'English')
    )
    
    question_text = models.CharField(max_length=255, unique=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    
    def __str__(self):
        return self.question_text

class SecurityAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(SecurityQuestion, on_delete=models.CASCADE)
    answer_hash = models.CharField(max_length=255)

    def set_answer(self, plain_answer):
        self.answer_hash = make_password(plain_answer)

    def check_answer(self, plain_answer):
        from django.contrib.auth.hashers import check_password
        return check_password(plain_answer, self.answer_hash)

    def save(self, *args, **kwargs):
        # Only validate if answer_hash is not empty
        if self.answer_hash and not is_password_usable(self.answer_hash):
            raise ValueError("Answers must be hashed using set_answer() method")
        super().save(*args, **kwargs)
        
    class Meta:
        unique_together = ('user', 'question')
    
    def __str__(self):
        return f"{self.user.phone} - {self.question.question_text[:20]}"

class Interest(models.Model):
    CATEGORY_CHOICES = (
        ('academic', 'Academic'),
        ('hobby', 'Hobby'),
        ('professional', 'Professional')
    )
    
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES)
    
    def __str__(self):
        return self.name
class University(models.Model):
    name = models.CharField(max_length=255, unique=True)
  
class StudyField(models.Model):
    name = models.CharField(max_length=255, unique=True)

class Profile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female')
    )
    
    ACADEMIC_STATUS_CHOICES = [
        ('high_school', 'High School'),
        ('undergraduate', 'Undergraduate'),
        ('graduate', 'Graduate'),
        ('not_studying', 'Not Currently Studying')
    ]
    
    academic_status = models.CharField(
        max_length=20,
        choices=ACADEMIC_STATUS_CHOICES,
        blank=True,
        null=True
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birth_date = models.DateField(blank=True, null=True)  # Made optional
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    address = models.TextField(blank=True, null=True)  # Optional
    interests = models.ManyToManyField(Interest, through='ProfileInterest', blank=True)
    university = models.ForeignKey(University, on_delete=models.SET_NULL, null=True, blank=True,default='Null', related_name='profiles')
    studyfield = models.ForeignKey(StudyField, on_delete=models.SET_NULL, null=True, blank=True,default='Null', related_name='profiles')

    def __str__(self):
        return self.user.get_full_name() or str(self.user)
    
    def clean(self):
        super().clean()
        
        # Rule 1: Birth date validation
        if self.birth_date and self.birth_date > timezone.now().date():
            raise ValidationError({"birth_date": "Birth date cannot be in the future."})

        # Rule 2: University/studyfield required for undergrad/graduate
        if self.academic_status in ["undergraduate", "graduate"]:
            if not self.university:
                raise ValidationError({"university": "Required for undergraduate/graduate students."})
            if not self.studyfield:
                raise ValidationError({"studyfield": "Required for undergraduate/graduate students."})
        else:
            self.university = None
            self.studyfield = None

        # Rule 3: Validate academic status transitions
        if self.pk:  # Only check if this is an existing profile (not new)
            old_status = Profile.objects.get(pk=self.pk).academic_status
            new_status = self.academic_status
            
            # Define allowed transitions
            allowed_transitions = {
                "high_school": ["undergraduate", "not_studying","high_school"],
                "undergraduate": ["graduate","undergraduate"],
                "not_studying": ["high_school","undergraduate","not_studying"],
                "graduate": ["graduate"],
            }
            
            if old_status in allowed_transitions and new_status not in allowed_transitions[old_status]:
                raise ValidationError(
                    {"academic_status": f"Cannot change status from {old_status} to {new_status}."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
            
class ProfileImage(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE,related_name='image')
    image = models.ImageField(upload_to='profile/images')   
    
    def clean(self):
        super().clean()

        # Max file size: 5MB (you can adjust this)
        max_file_size = 5 * 1024 * 1024
        if self.image.size > max_file_size:
            raise ValidationError("Image file too large ( > 5MB )")

        # Optionally validate dimensions (min/max)
        width, height = get_image_dimensions(self.image)
        if width < 300 or height < 300:
            raise ValidationError("Image is too small. Minimum dimensions are 300x300px.")

        if width > 5000 or height > 5000:
            raise ValidationError("Image is too large. Maximum dimensions are 5000x5000px.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Calls `clean()` before saving
        super().save(*args, **kwargs)

   
    
class ProfileInterest(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE)
    intensity = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    class Meta:
        unique_together = ('profile', 'interest')
    
    def __str__(self):
        return f"{self.profile.user.get_full_name} - {self.interest.name} ({self.intensity})"
  

class EWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet for {self.user.get_full_name}"
    
    def deposit(self, amount):
        """Deposit money into the wallet""" 
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive")
            
        self.current_balance += Decimal(amount).quantize(Decimal('0.00'))
        self.save()
        
    def withdraw(self, amount):
        """Withdraw money from the wallet"""
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive")
            
        amount = Decimal(amount).quantize(Decimal('0.00'))
        if self.current_balance < amount:
            raise ValidationError("Insufficient funds")
            
        self.current_balance -= amount
        self.save()
        
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        if self.current_balance < 0:
            raise ValidationError("Balance cannot be negative")


class DepositMethod(models.Model):
    METHOD_CHOICES = (
        ('bank_transfer', 'Bank Transfer'),
        ('money_transfer', 'Money Transfer')
    )
    
    name = models.CharField(max_length=20, choices=METHOD_CHOICES)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.get_name_display()


class BankTransferInfo(models.Model):
    deposit_method = models.ForeignKey(DepositMethod, on_delete=models.CASCADE, related_name='bank_info')
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    iban = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_name}"


class MoneyTransferInfo(models.Model):
    deposit_method = models.ForeignKey(DepositMethod, on_delete=models.CASCADE, related_name='transfer_info')
    company_name = models.CharField(max_length=100)
    receiver_name = models.CharField(max_length=255)
    receiver_phone = models.CharField(max_length=20)
    
    def __str__(self):
        return f"{self.company_name} - {self.receiver_name}"


class DepositRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected')
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_requests')
    deposit_method = models.ForeignKey(DepositMethod, on_delete=models.CASCADE)
    transaction_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    screenshot_path = models.ImageField(
        upload_to='deposit_screenshots/',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name} - {self.amount} ({self.get_status_display()})" 
    
    def approve(self):
        """Approve the deposit request"""
        if self.status != 'pending':
            raise ValidationError("Only pending requests can be approved")
            
        self.user.wallet.deposit(self.amount)
        self.status = 'verified'
        self.save()
        
    def reject(self):
        """Reject the deposit request"""
        if self.status != 'pending':
            raise ValidationError("Only pending requests can be rejected")
            
        self.status = 'rejected'
        self.save()
        
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError("Deposit amount must be positive")

@receiver(post_save, sender=DepositRequest)
def update_transaction_status(sender, instance, **kwargs):
    """Update transaction status when deposit request status changes"""
    try:
        transaction = Transaction.objects.get(reference_id=f"DEP-{instance.id}")
        
        # Map deposit request status to transaction status
        status_mapping = {
            'pending': 'pending',
            'verified': 'completed',
            'rejected': 'failed'
        }
        
        new_status = status_mapping.get(instance.status)
        if new_status and transaction.status != new_status:
            transaction.status = new_status
            transaction.save()
    except Transaction.DoesNotExist:
        pass  # Transaction might not exist yet or was deleted

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('course_payment', 'Course Payment'),
        ('course_refund', 'Course Refund'),
        ('transfer', 'Transfer')
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    )
    
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_transactions'
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transactions'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    description = models.TextField(blank=True)
    reference_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for the transaction (e.g., ENR-123 for enrollment payments)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} ({self.status})"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        if self.amount <= 0:
            raise ValidationError("Amount must be positive")
            
        # Different validation rules based on transaction type
        if self.transaction_type == 'deposit':
            if not self.receiver:
                raise ValidationError("Receiver is required for deposit transactions")
            # Sender can be null for deposits (external deposits)
            
        elif self.transaction_type == 'withdrawal':
            if not self.sender:
                raise ValidationError("Sender is required for withdrawal transactions")
            # Receiver can be null for withdrawals (external withdrawals)
            
        elif self.transaction_type in ['transfer', 'course_payment', 'course_refund']:
            if not self.sender or not self.receiver:
                raise ValidationError("Both sender and receiver are required for this transaction type")
            if self.sender == self.receiver:
                raise ValidationError("Sender and receiver cannot be the same")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('deposit_request', 'Deposit Request'),
        ('deposit_approved', 'Deposit Approved'),
        ('deposit_rejected', 'Deposit Rejected'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Store additional data like deposit_request_id
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} - {self.recipient.get_full_name()}"