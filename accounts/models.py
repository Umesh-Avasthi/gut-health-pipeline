from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username


class OTP(models.Model):
    phone = models.CharField(max_length=15)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.phone}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_verified and not self.is_expired()

    @staticmethod
    def generate_otp(phone):
        """Generate a 6-digit OTP and save it"""
        # Delete old OTPs for this phone
        OTP.objects.filter(phone=phone, is_verified=False).delete()
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        
        # Create OTP with 10 minutes expiration
        expires_at = timezone.now() + timedelta(minutes=10)
        
        otp = OTP.objects.create(
            phone=phone,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        return otp
