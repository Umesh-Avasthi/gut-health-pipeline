from django import forms
from django.core.validators import EmailValidator, RegexValidator
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from .models import Profile


class RegistrationForm(forms.Form):
    """Registration form with validation for name, email, and mobile number"""
    
    name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'id': 'name'
        }),
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z\s]+$',
                message='Name should only contain letters and spaces.',
                code='invalid_name'
            )
        ],
        error_messages={
            'required': 'Name is required.',
            'max_length': 'Name is too long (maximum 100 characters).'
        }
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'id': 'email'
        }),
        validators=[EmailValidator(message='Please enter a valid email address.')],
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter phone number (with country code)',
            'id': 'phone'
        }),
        error_messages={
            'required': 'Phone number is required.',
            'max_length': 'Phone number is too long (maximum 20 characters).'
        }
    )
    
    password = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'id': 'password'
        }),
        error_messages={
            'required': 'Password is required.',
            'min_length': 'Password must be at least 8 characters long.'
        }
    )
    
    def clean_email(self):
        """Check if email already exists (case-insensitive)"""
        email = self.cleaned_data.get('email')
        if email:
            email_lower = email.lower().strip()
            if User.objects.filter(username__iexact=email_lower).exists():
                raise forms.ValidationError('This email is already registered. Please login instead.')
        return email.lower().strip() if email else email
    
    def clean_phone(self):
        """Validate and clean phone number"""
        import re
        phone = self.cleaned_data.get('phone')
        
        if not phone:
            return phone
        
        # Remove spaces, dashes, parentheses, and other common formatting characters
        cleaned_phone = re.sub(r'[\s\-\(\)\.]', '', phone)
        
        # Validate phone number format (E.164 format: optional +, then 1-15 digits starting with 1-9)
        # Allow formats like: +1234567890, 1234567890, etc.
        if not re.match(r'^\+?[1-9]\d{6,14}$', cleaned_phone):
            raise forms.ValidationError(
                'Please enter a valid mobile number. '
                'Format: +1234567890 or 1234567890 (7-15 digits, with optional country code).'
            )
        
        # Check if phone number already exists
        if Profile.objects.filter(phone=cleaned_phone).exists():
            raise forms.ValidationError('Phone number already registered. Please login.')
        
        # Return cleaned phone number (normalized format)
        return cleaned_phone


class LoginForm(AuthenticationForm):
    """Login form with email validation"""
    
    username = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'id': 'id_username',
            'autofocus': True
        }),
        validators=[EmailValidator(message='Please enter a valid email address.')],
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        },
        label='Email'
    )
    
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'id': 'id_password'
        }),
        error_messages={
            'required': 'Password is required.'
        }
    )
    
    def clean_username(self):
        """Validate email format"""
        email = self.cleaned_data.get('username')
        if email:
            # Additional email validation
            EmailValidator()(email)
        return email
