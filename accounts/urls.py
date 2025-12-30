from django.urls import path
from django.contrib.auth import views as auth_views
from .views import register_view, dashboard_view, home, verify_otp_view, resend_otp_view, login_view, logout_view

urlpatterns = [
    path("", home, name="home"),
    path("register/", register_view, name="register"),
    path("verify-otp/", verify_otp_view, name="verify_otp"),
    path("resend-otp/", resend_otp_view, name="resend_otp"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
]
