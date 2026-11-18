from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        campus = extra.get("campus")
        if campus is not None and not isinstance(campus, models.Model):
            # createsuperuser --noinput passes the campus as its primary key.
            extra["campus_id"] = extra.pop("campus")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        # Staff are created by the operator (docs/OPERATIONS.md), who attests they are an adult.
        extra.setdefault("adult_attested_at", timezone.now())
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Email login, no username (plan 2.4, 3.1). Gender, age, car and residence from 2008 are gone."""

    class Classification(models.TextChoices):
        FRESHMAN = "freshman", "Freshman"
        SOPHOMORE = "sophomore", "Sophomore"
        JUNIOR = "junior", "Junior"
        SENIOR = "senior", "Senior"
        GRADUATE = "graduate", "Graduate"

    username = None
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=60)
    last_name = models.CharField("last name", max_length=60)
    campus = models.ForeignKey("meals.Campus", on_delete=models.PROTECT, related_name="users")
    # Optional; NULL is "not given" and the classification CHECK allows it.
    classification = models.CharField(  # noqa: DJ001
        max_length=10, choices=Classification.choices, null=True, blank=True
    )
    adult_attested_at = models.DateTimeField()

    USERNAME_FIELD = "email"
    # createsuperuser prompts for these; campus is asked for by id (see docs/OPERATIONS.md).
    REQUIRED_FIELDS = ["first_name", "last_name", "campus"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=Q(classification__isnull=True)
                | Q(classification__in=["freshman", "sophomore", "junior", "senior", "graduate"]),
                name="accounts_user_classification_valid",
            ),
        ]

    @property
    def public_name(self) -> str:
        """First name plus last initial: the only form shown to other users (AZ-06)."""
        return f"{self.first_name} {self.last_name[:1]}." if self.last_name else self.first_name

    def __str__(self) -> str:
        return self.email
