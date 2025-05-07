from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, SecurityQuestion, SecurityAnswer, Interest, 
    Profile, ProfileInterest, EWallet, DepositMethod,
    BankTransferInfo, MoneyTransferInfo, DepositRequest
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_active', 'last_login')
    list_filter = ('user_type', 'is_active')
    search_fields = ('username', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'user_type')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type'),
        }),
    )

@admin.register(SecurityQuestion)
class SecurityQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'language')
    list_filter = ('language',)
    search_fields = ('question_text',)

@admin.register(SecurityAnswer)
class SecurityAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question')
    list_filter = ('question',)
    search_fields = ('user__username',)

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
    list_display = ('full_name', 'user', 'gender', 'birth_date')
    list_filter = ('gender',)
    search_fields = ('full_name', 'user__username')
    inlines = (ProfileInterestInline,)

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