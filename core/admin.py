from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('get_full_name', 'phone', 'user_type', 'is_active', 'last_login')
    list_filter = ('user_type', 'is_active')
    search_fields = ('phone', 'first_name', 'middle_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined',)  # Add this line
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name',
                'middle_name',
                'last_name',
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
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
    plain_answer = forms.CharField(label="Answer", widget=forms.PasswordInput)

    class Meta:
        model = SecurityAnswer
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['plain_answer'].required = False

@admin.register(SecurityAnswer)
class SecurityAnswerAdmin(admin.ModelAdmin):
    form = SecurityAnswerForm
    list_display = ('user', 'question')
    exclude = ('answer_hash',)  # We'll handle this manually

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
    list_display = ('user', 'deposit_method', 'amount', 'status', 'created_at')
    list_filter = ('status', 'deposit_method')
    search_fields = ('user__username', 'transaction_number')