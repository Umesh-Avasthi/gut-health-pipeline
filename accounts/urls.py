from django.urls import path
from django.contrib.auth import views as auth_views
from .views import register_view, dashboard_view, home, login_view, logout_view

urlpatterns = [
    path("", home, name="home"),
    path("register/", register_view, name="register"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
]
