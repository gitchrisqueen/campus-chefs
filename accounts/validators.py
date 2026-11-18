from django.core.exceptions import ValidationError


class MaximumLengthValidator:
    """Caps password length (plan 2.4), so a huge password cannot make hashing expensive."""

    def __init__(self, max_length: int = 128):
        self.max_length = max_length

    def validate(self, password: str, user=None) -> None:
        if len(password) > self.max_length:
            raise ValidationError(
                f"This password is too long. Use at most {self.max_length} characters.",
                code="password_too_long",
            )

    def get_help_text(self) -> str:
        return f"Your password can’t be longer than {self.max_length} characters."
