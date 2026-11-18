from django.contrib.auth import views as auth_views
from django.urls import path

from core.ratelimit import limit_failed_logins

from . import views

urlpatterns = [
    path("register", views.register, name="register"),
    path("login", limit_failed_logins(views.LoginView.as_view()), name="login"),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),  # POST only (Django 5+)
    path("demo/login/<slug:persona>", views.demo_login, name="demo_login"),
    path("me", views.me, name="me"),
    path("me/edit", views.account_edit, name="account_edit"),
    path("me/password", views.PasswordChangeView.as_view(), name="password_change"),
    path("me/delete", views.account_delete, name="account_delete"),
]
