from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, OTP


# Inline Profile Admin (shows Profile in User admin)
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('phone',)


# Enhanced User Admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'get_phone', 'date_joined', 'last_login', 'is_active')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name')
    
    def get_phone(self, obj):
        try:
            return obj.profile.phone
        except Profile.DoesNotExist:
            return "No phone"
    get_phone.short_description = 'Phone Number'


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# Profile Admin
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'get_email', 'get_name', 'get_date_joined')
    list_filter = ('user__date_joined',)
    search_fields = ('user__username', 'user__email', 'phone', 'user__first_name')
    readonly_fields = ('user',)
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_name(self, obj):
        return obj.user.first_name
    get_name.short_description = 'Name'
    
    def get_date_joined(self, obj):
        return obj.user.date_joined
    get_date_joined.short_description = 'Date Joined'


# OTP Admin
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'otp_code', 'created_at', 'expires_at', 'is_verified', 'is_expired_status')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('phone', 'otp_code')
    readonly_fields = ('created_at', 'expires_at')
    ordering = ('-created_at',)
    
    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = 'Expired'
