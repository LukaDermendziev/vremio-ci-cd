"""
Django settings for the salon scheduler project.

PostgreSQL in production (via DATABASE_URL or POSTGRES_* env vars).
SQLite fallback for local development when no database env is set.
"""

from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from repo root (parent of backend/) if present
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR.parent / ".env")
except ImportError:
    pass


def _env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


DEV_SECRET_KEY = "dev-only-change-me-before-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEV_SECRET_KEY)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique value when DJANGO_DEBUG is False."
    )

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS")

_railway_public = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip().lower()
_site_url_explicit = os.environ.get("SITE_URL", "").strip().rstrip("/")
_use_railway_site = os.environ.get("USE_RAILWAY_SITE_URL", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Public URL for emails, verify links, and manage-booking links.
# During Railway testing: USE_RAILWAY_SITE_URL=True (uses *.up.railway.app).
# After custom domain is live: set SITE_URL=https://www.fancyfingers.mk and turn the flag off.
if _use_railway_site and _railway_public:
    SITE_URL = f"https://{_railway_public}"
elif _site_url_explicit:
    SITE_URL = _site_url_explicit
elif _railway_public and os.environ.get("RAILWAY_ENVIRONMENT"):
    SITE_URL = f"https://{_railway_public}"
else:
    SITE_URL = "http://127.0.0.1:8000"

# Public Vremio platform URL (footer "Powered by" on salon domains, etc.).
_platform_url = os.environ.get("PLATFORM_URL", "").strip().rstrip("/")
if _platform_url:
    PLATFORM_URL = _platform_url
elif _railway_public:
    PLATFORM_URL = f"https://{_railway_public}"
else:
    PLATFORM_URL = SITE_URL

# Salon-branded customer domain(s) — homepage redirects to CUSTOMER_DOMAIN_SALON_SLUG.
CUSTOMER_DOMAINS = _env_list("CUSTOMER_DOMAINS")
CUSTOMER_DOMAIN_SALON_SLUG = os.environ.get("CUSTOMER_DOMAIN_SALON_SLUG", "").strip()

for _host in CUSTOMER_DOMAINS:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

_railway_domain = _railway_public
if _railway_domain and _railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_domain)

# Railway internal healthchecks use localhost / private domain — not the public URL.
if os.environ.get("RAILWAY_ENVIRONMENT"):
    if ".up.railway.app" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".up.railway.app")
    for _host in (
        "localhost",
        "127.0.0.1",
        "healthcheck.railway.app",
        os.environ.get("RAILWAY_PRIVATE_DOMAIN", "").strip(),
    ):
        if _host and _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)
    if _railway_domain:
        _railway_origin = f"https://{_railway_domain}"
        if _railway_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_railway_origin)

if not DEBUG:
    for _host in ALLOWED_HOSTS:
        if _host in ("*", "localhost", "127.0.0.1") or _host.startswith("."):
            continue
        _origin = f"https://{_host}"
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "booking",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "booking.middleware.CustomerDomainMiddleware",
    "booking.middleware.DefaultMacedonianLocaleMiddleware",
    "booking.middleware.NeverCacheOwnerMiddleware",
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
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "booking.context_processors.language",
                "booking.context_processors.vremio",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ── Database ─────────────────────────────────────────────────────────────────
# Priority: DATABASE_URL → POSTGRES_* → SQLite (local dev)
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ["DATABASE_URL"],
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", ""),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 600,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    # collectstatic during Railway/Nixpacks build may run before DATABASE_URL exists.
    _build_phase = os.environ.get("DJANGO_BUILD") == "1"
    if not DEBUG and not _build_phase:
        raise ImproperlyConfigured(
            "PostgreSQL is required in production. Set DATABASE_URL or POSTGRES_DB."
        )


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "mk"

LANGUAGES = [
    ("mk", "Македонски"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "Europe/Skopje"

USE_I18N = True
USE_L10N = True

USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedStaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Rate limiting uses Django's cache backend (LocMem in dev; Redis recommended in production).
_cache_url = os.environ.get("CACHE_URL", "").strip()
if _cache_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _cache_url,
            "OPTIONS": {
                "socket_connect_timeout": 2,
                "socket_timeout": 2,
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    if not DEBUG:
        import warnings

        warnings.warn(
            "CACHE_URL is not set. Rate limiting uses per-process memory and is "
            "not reliable with multiple Gunicorn workers. Set CACHE_URL to a Redis URL.",
            stacklevel=1,
        )

MEDIA_URL = "media/"
_media_root = os.environ.get("MEDIA_ROOT", "")
MEDIA_ROOT = Path(_media_root) if _media_root else BASE_DIR / "media"

# Align with reference photo limit in booking policy (default 5 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/owner/login/"
LOGIN_REDIRECT_URL = "/owner/dashboard/"
LOGOUT_REDIRECT_URL = "/owner/login/"
PASSWORD_RESET_TIMEOUT = 86400  # 24 hours

# ── Email ──────────────────────────────────────────────────────────────────────
# Development: print emails to console. Production: set EMAIL_HOST_USER/PASSWORD or EMAIL_BACKEND.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "15"))
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
BREVO_SMS_SENDER = os.environ.get("BREVO_SMS_SENDER", "").strip()

_email_backend = os.environ.get("EMAIL_BACKEND", "").strip()
if _email_backend:
    EMAIL_BACKEND = _email_backend
elif BREVO_API_KEY:
    EMAIL_BACKEND = "booking.backends.brevo_api.BrevoAPIEmailBackend"
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if not DEBUG and "console" in EMAIL_BACKEND:
    import warnings

    warnings.warn(
        "EMAIL_BACKEND is console in production. Outgoing mail is logged only — "
        "set BREVO_API_KEY (recommended on Railway) or SMTP credentials.",
        stacklevel=1,
    )

if os.environ.get("RAILWAY_ENVIRONMENT") and "smtp" in EMAIL_BACKEND.lower():
    import warnings

    warnings.warn(
        "SMTP email on Railway requires a Pro plan — Hobby/Free block ports 587/465. "
        "Use BREVO_API_KEY with booking.backends.brevo_api.BrevoAPIEmailBackend instead.",
        stacklevel=1,
    )

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "Vremio Booking <noreply@vremio.app>"
)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
OWNER_NOTIFICATION_EMAIL = os.environ.get("OWNER_NOTIFICATION_EMAIL", "").strip()
VREMIO_CONTACT_EMAIL = os.environ.get("VREMIO_CONTACT_EMAIL", "").strip()

IMAGE_MODERATION_ENABLED = os.environ.get("IMAGE_MODERATION_ENABLED", "False") == "True"
IMAGE_MODERATION_PROVIDER = os.environ.get("IMAGE_MODERATION_PROVIDER", "").strip()

# ── Logging ────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "booking": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "booking.email": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Production security (when DEBUG=False) ─────────────────────────────────────
if not DEBUG:
    if os.environ.get("USE_SECURE_PROXY_SSL_HEADER", "True") == "True":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Railway terminates HTTPS at the edge; internal healthchecks use HTTP.
    _ssl_redirect_default = "False" if os.environ.get("RAILWAY_ENVIRONMENT") else "True"
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", _ssl_redirect_default) == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "False") == "True"
