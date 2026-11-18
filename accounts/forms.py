from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm, UsernameField
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from meals.models import CookProfile

from .models import User

ALREADY_REGISTERED = "This email is already registered."


def _email_taken(email: str, exclude_pk: int | None = None) -> bool:
    return User.objects.filter(email__iexact=email).exclude(pk=exclude_pk).exists()


class LoginForm(AuthenticationForm):
    """Same message for a wrong password, an unknown email and an inactive account (AUTH-02)."""

    username = UsernameField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))
    error_messages = {
        "invalid_login": "Email or password is incorrect.",
        "inactive": "Email or password is incorrect.",
    }


class RegistrationForm(BaseUserCreationForm):
    ROLE_CHOICES = [("eat", "I want to eat"), ("cook", "I also cook")]

    adult = forms.BooleanField(
        label="I am 18 or older",
        error_messages={"required": "You must be 18 or older to use Campus Chefs."},
    )
    role = forms.ChoiceField(label="How will you use Campus Chefs?", choices=ROLE_CHOICES, widget=forms.RadioSelect)
    food_safety = forms.BooleanField(
        label="Cooks: I will cook in a clean kitchen and declare every allergen in my dishes",
        required=False,
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "campus", "classification"]

    def clean_email(self) -> str:
        email = self.cleaned_data["email"]
        if _email_taken(email):
            raise ValidationError(ALREADY_REGISTERED)
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("role") == "cook" and not cleaned.get("food_safety"):
            self.add_error("food_safety", "Cooks must accept the food-safety acknowledgement.")
        return cleaned

    def save(self, commit: bool = True) -> User:
        now = timezone.now()
        self.instance.adult_attested_at = now
        with transaction.atomic():
            user = super().save(commit=True)
            if self.cleaned_data["role"] == "cook":
                CookProfile.objects.create(user=user, food_safety_ack_at=now)
        return user


class AccountForm(forms.ModelForm):
    """Account edit. Changing the email needs the current password (ACCT-04)."""

    current_password = forms.CharField(
        label="Current password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Needed only when you change your email.",
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "campus", "classification"]

    def clean_email(self) -> str:
        email = self.cleaned_data["email"]
        if _email_taken(email, exclude_pk=self.instance.pk):
            raise ValidationError(ALREADY_REGISTERED)
        return email

    def clean(self):
        cleaned = super().clean()
        if "email" in self.changed_data and not self.instance.check_password(cleaned.get("current_password") or ""):
            self.add_error("current_password", "Enter your current password to change your email.")
        return cleaned


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user: User, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise ValidationError("Your password is incorrect.")
        return password
