from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from core import seed_data

from . import services
from .forms import AccountForm, DeleteAccountForm, LoginForm, RegistrationForm, ShortHelpPasswordChangeForm
from .models import User

MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
DEMO_PERSONAS = {
    "cook": seed_data.PERSONA_COOK[0],
    "diner": seed_data.PERSONA_DINER[0],
    "cook2": seed_data.PERSONA_COOK2[0],
}


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm


class PasswordChangeView(auth_views.PasswordChangeView):
    """Django's view keeps this session (update_session_auth_hash) and ends the others."""

    template_name = "accounts/password.html"
    form_class = ShortHelpPasswordChangeForm
    success_url = reverse_lazy("me")

    def form_valid(self, form):
        messages.success(self.request, "Your password was changed.")
        return super().form_valid(form)


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def register(request):
    if not settings.CC_REGISTRATION_OPEN:
        raise Http404
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if form.is_bound and form.is_valid():
        user = form.save()
        login(request, user, backend=MODEL_BACKEND)
        return redirect("me")
    return render(request, "accounts/register.html", {"form": form})


def demo_login(request, persona):
    """POST /demo/login/<persona>: one click into a seeded account. 404 unless CC_DEMO_MODE."""
    if not settings.CC_DEMO_MODE or persona not in DEMO_PERSONAS:
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    user = get_object_or_404(User, email=DEMO_PERSONAS[persona], is_active=True)
    login(request, user, backend=MODEL_BACKEND)
    return redirect("me")


@login_required
@require_GET
def me(request):
    return render(request, "accounts/me.html", {"is_cook": hasattr(request.user, "cook_profile")})


@login_required
@sensitive_post_parameters("current_password")
@require_http_methods(["GET", "POST"])
def account_edit(request):
    # A fresh instance, so a rejected edit never changes request.user in memory.
    account = User.objects.get(pk=request.user.pk)
    form = AccountForm(request.POST if request.method == "POST" else None, instance=account)
    if form.is_bound and form.is_valid():
        form.save()
        messages.success(request, "Your account was updated.")
        return redirect("me")
    return render(request, "accounts/edit.html", {"form": form})


@login_required
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def account_delete(request):
    form = DeleteAccountForm(request.user, request.POST if request.method == "POST" else None)
    if form.is_bound and hasattr(request.user, "cook_profile"):
        # The cook path (cancel open offerings, release bookings, clear the bio) lands with
        # ACCT-03 in phase 6. Until then, refuse rather than leave orphaned live offerings.
        messages.error(request, "Cook accounts cannot be deleted yet. This arrives with bookings (phase 6).")
        return render(request, "accounts/delete.html", {"form": form}, status=409)
    if form.is_bound and form.is_valid():
        services.delete_account(request.user)
        logout(request)
        messages.success(request, "Your account was deleted.")
        return redirect("home")
    return render(request, "accounts/delete.html", {"form": form})
