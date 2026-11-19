"""Django settings for Campus Chefs.

Production-safe by default. The local compose demo opts into plain HTTP with
CC_DEMO_LOCAL_HTTP=true, which is only allowed for loopback hosts (SEC-09).
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

from core.secrets import env_bool, env_list, read_secret

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = read_secret("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE must be set")

DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,web")

# Demo switches
CC_DEMO_MODE = env_bool("CC_DEMO_MODE", default=False)
CC_DEMO_LOCAL_HTTP = env_bool("CC_DEMO_LOCAL_HTTP", default=False)
CC_REGISTRATION_OPEN = env_bool("CC_REGISTRATION_OPEN", default=True)
CC_AI_ENABLED = env_bool("CC_AI_ENABLED", default=False)
CC_FEEDBACK_URL = read_secret("CC_FEEDBACK_URL", "") or ""

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]", "web"}
if CC_DEMO_LOCAL_HTTP and not set(ALLOWED_HOSTS) <= LOOPBACK_HOSTS:
    raise ImproperlyConfigured(
        "CC_DEMO_LOCAL_HTTP=true is only allowed when DJANGO_ALLOWED_HOSTS is loopback-only "
        f"({', '.join(sorted(LOOPBACK_HOSTS))})"
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "core",
    "accounts",
    "meals",
    "bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "core.middleware.PermissionsPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.NoStoreForAuthenticatedMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.demo",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": read_secret("DB_HOST", "db"),
        "PORT": read_secret("DB_PORT", "5432"),
        "NAME": read_secret("DB_NAME", "campuschefs"),
        "USER": read_secret("DB_USER", "campuschefs_app"),
        "PASSWORD": read_secret("DB_PASSWORD", ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 3},
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    # Failed-login counters (phase 3). Its own table, so a flood of keys cannot cull them.
    "ratelimit": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cc_ratelimit",
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    },
}

AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "accounts.validators.MaximumLengthValidator", "OPTIONS": {"max_length": 128}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "me"
LOGOUT_REDIRECT_URL = "home"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.NONE],
}
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"

# Browsers ignore COOP on plain-HTTP origins (and log an error), so it is sent only over HTTPS.
SECURE_CROSS_ORIGIN_OPENER_POLICY = None if CC_DEMO_LOCAL_HTTP else "same-origin"

if not CC_DEMO_LOCAL_HTTP:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
