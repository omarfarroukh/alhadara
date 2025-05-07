from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        if not username:
            raise ValueError('Username is required')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'admin')
        
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('reception', 'Reception'),
        ('admin', 'Admin')
    )
    
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['email']
    
    def __str__(self):
        return self.username


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_answers')
    question = models.ForeignKey(SecurityQuestion, on_delete=models.CASCADE)
    answer_hash = models.CharField(max_length=255)
    
    class Meta:
        unique_together = ('user', 'question')
    
    def __str__(self):
        return f"{self.user.username} - {self.question.question_text[:20]}"


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


class Profile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    national_id = models.CharField(max_length=20)
    address = models.TextField()
    interests = models.ManyToManyField(Interest, through='ProfileInterest')
    
    def __str__(self):
        return self.full_name


class ProfileInterest(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE)
    intensity = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    class Meta:
        unique_together = ('profile', 'interest')
    
    def __str__(self):
        return f"{self.profile.full_name} - {self.interest.name} ({self.intensity})"


class EWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Wallet for {self.user.username}"


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
    screenshot_path = models.ImageField(upload_to='deposit_screenshots/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    wallet = models.ForeignKey(EWallet, on_delete=models.CASCADE, related_name='deposit_requests')
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.get_status_display()})" 