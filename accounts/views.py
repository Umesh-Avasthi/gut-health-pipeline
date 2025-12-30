from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from .models import Profile, OTP
from .utils import send_otp_sms
from .forms import RegistrationForm, LoginForm

def home(request):
    # Check if user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Get last logged-in user info from cookie (persists across logout)
    last_login_email = request.COOKIES.get('last_login_email', None)
    
    last_user = None
    if last_login_email:
        try:
            last_user = User.objects.get(username=last_login_email)
        except User.DoesNotExist:
            # User doesn't exist anymore, cookie will be ignored
            last_user = None
    
    return render(request, 'accounts/home.html', {
        'last_user': last_user
    })


# ---------------- REGISTER ----------------
def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        
        if form.is_valid():
            name = form.cleaned_data.get("name")
            email = form.cleaned_data.get("email")
            phone = form.cleaned_data.get("phone")
            password = form.cleaned_data.get("password")

            # ✅ GENERATE AND SEND OTP
            otp = OTP.generate_otp(phone)
            
            # Send OTP via SMS
            if send_otp_sms(phone, otp.otp_code):
                # Store registration data in session (including OTP for testing)
                request.session['registration_data'] = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'password': password,
                    'otp_code': otp.otp_code  # Store OTP in session for testing (remove in production)
                }
                messages.success(request, f"OTP sent to {phone}. Please check your phone or console.")
                return redirect("verify_otp")
            else:
                return render(request, "accounts/register.html", {
                    "form": form,
                    "error": "Failed to send OTP. Please try again."
                })
        else:
            # Form has validation errors
            return render(request, "accounts/register.html", {
                "form": form
            })
    
    # GET request - show empty form
    form = RegistrationForm()
    return render(request, "accounts/register.html", {
        "form": form
    })


# ---------------- VERIFY OTP ----------------
def verify_otp_view(request):
    # Check if registration data exists in session
    registration_data = request.session.get('registration_data')
    
    if not registration_data:
        messages.error(request, "Registration session expired. Please register again.")
        return redirect("register")
    
    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        phone = registration_data.get('phone')
        
        if not entered_otp:
            return render(request, "accounts/verify_otp.html", {
                "error": "Please enter OTP",
                "phone": phone
            })
        
        # Find valid OTP for this phone
        try:
            otp = OTP.objects.filter(phone=phone, is_verified=False).latest('created_at')
            
            if otp.is_expired():
                return render(request, "accounts/verify_otp.html", {
                    "error": "OTP has expired. Please request a new one.",
                    "phone": phone
                })
            
            if otp.otp_code == entered_otp:
                # OTP is correct, mark as verified
                otp.is_verified = True
                otp.save()
                
                # Create user
                name = registration_data.get('name')
                email = registration_data.get('email')
                password = registration_data.get('password')
                phone = registration_data.get('phone')
                
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=name
                )
                
                Profile.objects.create(user=user, phone=phone)
                
                # Clear session data
                del request.session['registration_data']
                
                messages.success(request, "Registration successful! Please login.")
                return redirect("login")
            else:
                return render(request, "accounts/verify_otp.html", {
                    "error": "Invalid OTP. Please try again.",
                    "phone": phone
                })
                
        except OTP.DoesNotExist:
            return render(request, "accounts/verify_otp.html", {
                "error": "OTP not found. Please request a new one.",
                "phone": phone
            })
    
    # GET request - show OTP verification form
    phone = registration_data.get('phone')
    # For development: Show OTP in template (remove in production)
    dev_otp = registration_data.get('otp_code') if settings.DEBUG else None
    return render(request, "accounts/verify_otp.html", {
        "phone": phone,
        "dev_otp": dev_otp  # Only show in DEBUG mode
    })


# ---------------- RESEND OTP ----------------
def resend_otp_view(request):
    if request.method != "POST":
        return redirect("register")
    
    registration_data = request.session.get('registration_data')
    
    if not registration_data:
        messages.error(request, "Registration session expired. Please register again.")
        return redirect("register")
    
    phone = registration_data.get('phone')
    
    # Generate new OTP
    otp = OTP.generate_otp(phone)
    
    if send_otp_sms(phone, otp.otp_code):
        messages.success(request, f"New OTP sent to {phone}.")
    else:
        messages.error(request, "Failed to send OTP. Please try again.")
    
    return redirect("verify_otp")


# ---------------- LOGIN ----------------
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        
        if form.is_valid():
            email = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(username=email, password=password)
            if user:
                login(request, user)
                # Store last logged-in user info in cookie (persists across logout)
                response = redirect("dashboard")
                response.set_cookie('last_login_email', user.username, max_age=60*60*24*30)  # 30 days
                return response

            # Authentication failed
            return render(request, "registration/login.html", {
                "form": form,
                "error": "Invalid email or password"
            })
        else:
            # Form has validation errors
            return render(request, "registration/login.html", {
                "form": form
            })

    # GET request - show form (optionally pre-filled with email from query parameter)
    email = request.GET.get('email', None)
    form = LoginForm(initial={'username': email} if email else {})
    return render(request, "registration/login.html", {
        "form": form
    })


# ---------------- DASHBOARD ----------------
@login_required
def dashboard_view(request):
    from fasta_processor.forms import FastaFileUploadForm
    from fasta_processor.models import FastaFile, ProcessingJob
    from fasta_processor.services import start_next_job_in_queue
    from django.utils import timezone
    from datetime import timedelta
    import os
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Handle upload POST request
    if request.method == 'POST' and 'files' in request.FILES:
        uploaded_files_list = request.FILES.getlist('files')
        
        # Validate number of files
        if not uploaded_files_list:
            messages.error(request, 'Please select at least one file to upload.')
        elif len(uploaded_files_list) > 3:
            messages.error(request, f'You can upload a maximum of 3 files at once. You selected {len(uploaded_files_list)} files.')
        else:
            # Validate each file
            valid_extensions = ['.fasta', '.fa', '.fas', '.fna', '.ffn', '.faa', '.frn']
            max_size = 100 * 1024 * 1024  # 100MB
            valid_files = True
            
            for file in uploaded_files_list:
                if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                    messages.error(request, f'Invalid file type for "{file.name}". Please upload a FASTA file.')
                    valid_files = False
                    break
                if file.size > max_size:
                    messages.error(request, f'File "{file.name}" exceeds 100MB. Your file is {file.size / (1024*1024):.2f}MB')
                    valid_files = False
                    break
            
            if valid_files:
                description = request.POST.get('description', '')
                uploaded_files = []
                
                for file in uploaded_files_list:
                    fasta_file = FastaFile(
                        user=request.user,
                        file=file,
                        original_filename=file.name,
                        file_size=file.size,
                        description=description if description else ''
                    )
                    fasta_file.save()
                    uploaded_files.append(fasta_file)
                    
                    job, created = ProcessingJob.objects.get_or_create(
                        fasta_file=fasta_file,
                        defaults={
                            'user': request.user,
                            'status': 'pending'
                        }
                    )
                
                started_job = start_next_job_in_queue()
                pending_count = ProcessingJob.objects.filter(status='pending').count()
                running_count = ProcessingJob.objects.filter(status='running').count()
                
                if len(uploaded_files) == 1:
                    if running_count > 0:
                        messages.success(request, f'File "{uploaded_files[0].original_filename}" uploaded successfully! Added to queue. {pending_count} file(s) waiting to process.')
                    else:
                        messages.success(request, f'File "{uploaded_files[0].original_filename}" uploaded successfully! Processing started.')
                else:
                    file_names = ', '.join([f'"{f.original_filename}"' for f in uploaded_files])
                    if running_count > 0:
                        messages.success(request, f'{len(uploaded_files)} files uploaded successfully! ({file_names}) Added to queue. {pending_count} file(s) waiting to process.')
                    else:
                        messages.success(request, f'{len(uploaded_files)} files uploaded successfully! ({file_names}) Processing started.')
                
                # Redirect to dashboard with jobs tab active
                return redirect('dashboard')
    
    # Get upload form context
    form = FastaFileUploadForm()
    
    running_jobs = ProcessingJob.objects.filter(
        user=request.user,
        status='running',
        started_at__gt=timezone.now() - timedelta(hours=6)
    )
    
    has_running_job = running_jobs.exists()
    running_job_info = None
    if has_running_job:
        running_job = running_jobs.first()
        running_job_info = {
            'filename': running_job.fasta_file.original_filename,
            'started_at': running_job.started_at
        }
    
    # Get jobs context
    fasta_files = FastaFile.objects.filter(user=request.user)
    jobs = ProcessingJob.objects.filter(user=request.user).order_by('-started_at')[:5]
    
    # Categorize jobs
    completed_files = fasta_files.filter(status='completed')
    incomplete_files = fasta_files.filter(status__in=['failed', 'uploaded'])
    processing_file_ids = set()
    processing_file_ids.update(fasta_files.filter(status='processing').values_list('id', flat=True))
    processing_file_ids.update(fasta_files.filter(job__status__in=['pending', 'running']).values_list('id', flat=True))
    processing_files = fasta_files.filter(id__in=processing_file_ids)
    
    return render(request, "dashboard.html", {
        "name": request.user.first_name,
        "upload_form": form,
        "has_running_job": has_running_job,
        "running_job_info": running_job_info,
        "fasta_files": fasta_files,
        "jobs": jobs,
        "completed_files": completed_files,
        "incomplete_files": incomplete_files,
        "processing_files": processing_files,
    })


# ---------------- LOGOUT ----------------
def logout_view(request):
    logout(request)
    # Last login info is stored in cookie, so it persists across logout
    return redirect("home")
