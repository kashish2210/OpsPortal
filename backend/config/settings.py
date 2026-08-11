"""
Django settings for the Fundsroom OpsPortal (Mini ERP + CRM) backend.

Every environment-specific value is read from environment variables (a local
``.env`` file is loaded automatically when present) so the exact same image can
run in development, Docker and production without code changes.

See ``.env.example`` for the full list of supported variables.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, "django-insecure-change-me-in-production"),
    ALLOWED_HOSTS=(list, ["*"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOW_ALL_ORIGINS=(bool, False),
    DATABASE_URL=(str, ""),
    TIME_ZONE=(str, "Asia/Kolkata"),
    SIGNUP_OPEN=(bool, True),
    REQUIRE_EMAIL_VERIFICATION=(bool, False),
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    EMAIL_HOST=(str, ""),
    EMAIL_PORT=(int, 587),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_USE_SSL=(bool, False),
    EMAIL_TIMEOUT=(int, 15),
    DEFAULT_FROM_EMAIL=(str, "OpsPortal <no-reply@opsportal.local>"),
    SERVER_EMAIL=(str, "OpsPortal <no-reply@opsportal.local>"),
    # -- media storage (bonus) ---------------------------------------------
    # local | cloudinary | s3   (see the STORAGES block further down)
    MEDIA_STORAGE=(str, "local"),
    CLOUDINARY_CLOUD_NAME=(str, ""),
    CLOUDINARY_API_KEY=(str, ""),
    CLOUDINARY_API_SECRET=(str, ""),
    CLOUDINARY_URL=(str, ""),
    CLOUDINARY_FOLDER=(str, "opsportal"),
    # Legacy switch, still honoured: USE_S3=True implies MEDIA_STORAGE=s3.
    USE_S3=(bool, False),
    AWS_ACCESS_KEY_ID=(str, ""),
    AWS_SECRET_ACCESS_KEY=(str, ""),
    AWS_STORAGE_BUCKET_NAME=(str, ""),
    AWS_S3_REGION_NAME=(str, "ap-south-1"),
    AWS_S3_CUSTOM_DOMAIN=(str, ""),
    AWS_S3_ENDPOINT_URL=(str, ""),
    AWS_QUERYSTRING_AUTH=(bool, True),
    AWS_QUERYSTRING_EXPIRE=(int, 3600),
    FRONTEND_URL=(str, "http://localhost:8080"),
    SECURE_SSL_REDIRECT=(bool, False),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    SEED_DEMO_DATA=(bool, False),
)

# Load .env from the backend directory, then from the repository root.
for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
    if candidate.exists():
        environ.Env.read_env(str(candidate))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# The public URL of the SPA. Used to build password-reset / verification links
# and to whitelist CORS during development.
FRONTEND_URL = env("FRONTEND_URL").rstrip("/")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local
    "core",
    "accounts",
    "crm",
    "inventory",
    "sales",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL wins when supplied (Docker / Render / Neon / Supabase ...).
# Falls back to a local SQLite file so `python manage.py runserver` works with
# zero infrastructure.
if env("DATABASE_URL"):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["CONN_MAX_AGE"] = 60
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # Allows logging in with either username or e-mail address.
    "accounts.backends.UsernameOrEmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/profile/"
# Deliberately no LOGOUT_REDIRECT_URL: it would short-circuit LogoutView and
# skip the "signed out" confirmation page.

# Feature flags used by the server-rendered auth pages.
SIGNUP_OPEN = env("SIGNUP_OPEN")
REQUIRE_EMAIL_VERIFICATION = env("REQUIRE_EMAIL_VERIFICATION")

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Media storage - product images and avatars.
#
# Everything is written through Django's storage API, so switching provider is
# an env change with no code change:
#
#   MEDIA_STORAGE=local       the media/ volume (default; zero setup)
#   MEDIA_STORAGE=cloudinary  Cloudinary - 25 GB free, image CDN + transforms
#   MEDIA_STORAGE=s3          Amazon S3, or any S3-compatible provider
#                             (Cloudflare R2, Backblaze B2, MinIO) via
#                             AWS_S3_ENDPOINT_URL
#
# See docs/ENVIRONMENT.md for where to obtain each provider's credentials.
# ---------------------------------------------------------------------------
MEDIA_STORAGE = env("MEDIA_STORAGE").strip().lower()

# Legacy switch kept working: USE_S3=True is the same as MEDIA_STORAGE=s3.
USE_S3 = env("USE_S3")
if USE_S3 and MEDIA_STORAGE == "local":
    MEDIA_STORAGE = "s3"

if MEDIA_STORAGE not in ("local", "cloudinary", "s3"):
    raise ImproperlyConfigured(
        f"MEDIA_STORAGE must be one of local, cloudinary or s3 - got {MEDIA_STORAGE!r}."
    )

if MEDIA_STORAGE == "cloudinary":
    # The SDK accepts either one CLOUDINARY_URL or the three parts separately;
    # support both so people can paste whichever the dashboard gave them.
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
        "API_KEY": env("CLOUDINARY_API_KEY"),
        "API_SECRET": env("CLOUDINARY_API_SECRET"),
        # Namespace everything so the account stays tidy if it is shared.
        "PREFIX": env("CLOUDINARY_FOLDER"),
        # Always build https:// URLs; a mixed-content image is invisible in
        # production until someone opens the console.
        "SECURE": True,
        # Keep our own uploaded filename instead of a random public_id, so
        # objects stay greppable against the product SKU.
        "MAGIC_FILE_PATH": "magic",
    }

    if env("CLOUDINARY_URL"):
        # cloudinary reads this from the process environment directly.
        os.environ.setdefault("CLOUDINARY_URL", env("CLOUDINARY_URL"))
    elif not all(CLOUDINARY_STORAGE[k] for k in ("CLOUD_NAME", "API_KEY", "API_SECRET")):
        raise ImproperlyConfigured(
            "MEDIA_STORAGE=cloudinary needs CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET (or CLOUDINARY_URL)."
        )

    INSTALLED_APPS = [*INSTALLED_APPS, "cloudinary", "cloudinary_storage"]

    _default_storage = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

elif MEDIA_STORAGE == "s3":
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
    AWS_QUERYSTRING_AUTH = env("AWS_QUERYSTRING_AUTH")
    AWS_QUERYSTRING_EXPIRE = env("AWS_QUERYSTRING_EXPIRE")
    AWS_S3_FILE_OVERWRITE = False
    # R2 and B2 reject ACLs outright; on S3 this defers to the bucket policy.
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_S3_SIGNATURE_VERSION = "s3v4"

    # A CDN hostname in front of the bucket: CloudFront, or an R2 custom domain
    # / r2.dev subdomain. Pair with AWS_QUERYSTRING_AUTH=False for stable,
    # cacheable URLs instead of expiring pre-signed ones.
    if env("AWS_S3_CUSTOM_DOMAIN"):
        AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN")

    # Any non-AWS S3-compatible endpoint (R2, B2, MinIO, LocalStack).
    if env("AWS_S3_ENDPOINT_URL"):
        AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
        # botocore >= 1.36 adds a CRC32 checksum to every upload by default.
        # Several S3-compatible providers reject the unfamiliar header with an
        # opaque 400, so relax it to "when_required" - but only for non-AWS
        # endpoints, leaving real S3 on the stricter default.
        os.environ.setdefault("AWS_REQUEST_CHECKSUM_CALCULATION", "when_required")
        os.environ.setdefault("AWS_RESPONSE_CHECKSUM_VALIDATION", "when_required")

    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {"location": "media", "default_acl": None},
    }
else:
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Session auth lets the browsable API and the Django-rendered pages
        # share the same backend during development.
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"login": "20/min", "password_reset": "10/hour"},
    "DATETIME_FORMAT": "iso-8601",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fundsroom OpsPortal API",
    "DESCRIPTION": (
        "Mini ERP + CRM operations portal. Customers (CRM), products and stock "
        "(inventory), and sales challans with stock-deduction business rules."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS") or [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# E-mail (SMTP)
# ---------------------------------------------------------------------------
# Three supported modes, all driven by env vars:
#   console  - prints to stdout (default for `manage.py runserver`)
#   smtp     - a real SMTP server. Docker Compose runs Mailpit on mailpit:1025
#              with a web inbox at http://localhost:8025, so the whole
#              password-reset / verification flow is testable end to end.
#   smtp+TLS - a production provider (SendGrid, Brevo, SES, Gmail, ...)
EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_USE_SSL = env("EMAIL_USE_SSL")
EMAIL_TIMEOUT = env("EMAIL_TIMEOUT")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = env("SERVER_EMAIL")

# TLS and SSL are mutually exclusive; TLS (STARTTLS on 587) wins if both are on.
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    EMAIL_USE_SSL = False

# Only applies to mail_admins()/mail_managers() error reports; the transactional
# templates set their own subjects.
EMAIL_SUBJECT_PREFIX = "[OpsPortal] "

# ---------------------------------------------------------------------------
# Security (only tightened when DEBUG is off)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
    SESSION_COOKIE_SECURE = env("SECURE_SSL_REDIRECT")
    CSRF_COOKIE_SECURE = env("SECURE_SSL_REDIRECT")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        "opsportal": {"level": "DEBUG" if DEBUG else "INFO", "handlers": ["console"], "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
# CI overrides these so the run emits JUnit XML, which GitHub Actions turns
# into a per-test report and inline annotations on the pull request:
#   TEST_RUNNER=xmlrunner.extra.djangotestrunner.XMLTestRunner
#   TEST_OUTPUT_DIR=test-results
TEST_RUNNER = env("TEST_RUNNER", default="django.test.runner.DiscoverRunner")
TEST_OUTPUT_DIR = env("TEST_OUTPUT_DIR", default="test-results")
TEST_OUTPUT_VERBOSE = 2
TEST_OUTPUT_FILE_NAME = "junit.xml"

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
#: Largest product image / avatar we accept (enforced in the serializers too).
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------------
# Project specific
# ---------------------------------------------------------------------------
SITE_NAME = "OpsPortal"
SITE_TAGLINE = "Mini ERP + CRM Operations Portal"
COMPANY_NAME = env("COMPANY_NAME", default="Fundsroom Distribution Pvt Ltd")
COMPANY_ADDRESS = env("COMPANY_ADDRESS", default="Unit 4, Trade Centre, Andheri East, Mumbai 400059")
COMPANY_GSTIN = env("COMPANY_GSTIN", default="27AAPFU0939F1ZV")
COMPANY_PHONE = env("COMPANY_PHONE", default="+91 22 4000 1234")
COMPANY_EMAIL = env("COMPANY_EMAIL", default="accounts@fundsroom.local")
