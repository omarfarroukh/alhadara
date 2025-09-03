from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest,
    University,StudyField, Transaction
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'get_full_name',
        'phone',
        'user_type',
        'is_verified',   # NEW
        'is_active',
        'last_login'
    )
    list_filter = ('user_type', 'is_active', 'is_verified')  # NEW
    search_fields = ('phone', 'first_name', 'middle_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined',)

    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
                'telegram_chat_id',  # NEW
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'is_verified',  # NEW
                'user_type',
                'groups',
                'user_permissions',
            )
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone',
                'first_name',
                'middle_name',
                'last_name',
                'password1',
                'password2',
                'user_type',
                'is_verified',  # NEW
                'telegram_chat_id',  # NEW
            ),
        }),
    )

    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'
       
@admin.register(SecurityQuestion)
class SecurityQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'language')
    list_filter = ('language',)
    search_fields = ('question_text',)

class SecurityAnswerForm(forms.ModelForm):
    plain_answer = forms.CharField(
        label="Answer", 
        widget=forms.PasswordInput(render_value=True),
        required=False
    )

    class Meta:
        model = SecurityAnswer
        fields = ['user', 'question', 'plain_answer']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize user display to show phone instead of username
        self.fields['user'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.phone})"
@admin.register(SecurityAnswer)
class SecurityAnswerAdmin(admin.ModelAdmin):
    form = SecurityAnswerForm
    list_display = ('get_user_phone', 'get_user_name', 'question')
    exclude = ('answer_hash',)
    list_select_related = ('user', 'question')
    search_fields = ('user__phone', 'user__first_name', 'question__question_text')
    list_filter = ('question', 'user__user_type')

    def get_user_phone(self, obj):
        return obj.user.phone
    get_user_phone.short_description = 'Phone'
    get_user_phone.admin_order_field = 'user__phone'

    def get_user_name(self, obj):
        return obj.user.get_full_name()
    get_user_name.short_description = 'User'
    get_user_name.admin_order_field = 'user__first_name'

    def save_model(self, request, obj, form, change):
        if 'plain_answer' in form.cleaned_data and form.cleaned_data['plain_answer']:
            obj.set_answer(form.cleaned_data['plain_answer'])
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'question')
    form = SecurityAnswerForm
    list_display = ('get_user_phone', 'question')  # Changed from 'phone'
    exclude = ('answer_hash',)
    list_select_related = ('user', 'question')  # Optimizes database queries

    def get_user_phone(self, obj):
        """Custom method to display user's phone number"""
        return obj.user.phone
    get_user_phone.short_description = 'Phone'  # Sets column header
    get_user_phone.admin_order_field = 'user__phone'  # Allows sorting

    def save_model(self, request, obj, form, change):
        if 'plain_answer' in form.cleaned_data and form.cleaned_data['plain_answer']:
            obj.set_answer(form.cleaned_data['plain_answer'])
        super().save_model(request, obj, form, change)
@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)

class ProfileInterestInline(admin.TabularInline):
    model = ProfileInterest
    extra = 1

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user_full_name', 'user', 'gender', 'birth_date')
    list_filter = ('gender',)
    search_fields = ('user__first_name', 'user__middle_name', 'user__last_name', 'user__phone')
    inlines = (ProfileInterestInline,)
    
    def user_full_name(self, obj):
        """Display the full name from the related User model"""
        return obj.user.get_full_name()
    user_full_name.short_description = 'Full Name'
    
    def get_queryset(self, request):
        """Optimize queries by selecting related User"""
        return super().get_queryset(request).select_related('user')
    
    
@admin.register(EWallet)
class EWalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_balance', 'last_updated')
    search_fields = ('user__username',)

@admin.register(DepositMethod)
class DepositMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)

@admin.register(BankTransferInfo)
class BankTransferInfoAdmin(admin.ModelAdmin):
    list_display = ('deposit_method', 'bank_name', 'account_name')
    list_filter = ('deposit_method',)
    search_fields = ('bank_name', 'account_name')

@admin.register(MoneyTransferInfo)
class MoneyTransferInfoAdmin(admin.ModelAdmin):
    list_display = ('deposit_method', 'company_name', 'receiver_name')
    list_filter = ('deposit_method',)
    search_fields = ('company_name', 'receiver_name')

@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    x=10
    list_display = ('user', 'deposit_method', 'amount', 'status', 'created_at')
    list_filter = ('status', 'deposit_method')
    search_fields = ('user__username', 'transaction_number')

@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display =['name']
    
@admin.register(StudyField)
class StudyFieldAdmin(admin.ModelAdmin):
    list_display =['name']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference_id', 'transaction_type', 'amount', 'sender', 
        'receiver', 'status', 'created_at'
    )
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = (
        'reference_id', 'sender__first_name', 'sender__last_name',
        'receiver__first_name', 'receiver__last_name', 'description'
    )
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'sender', 'receiver'
        )