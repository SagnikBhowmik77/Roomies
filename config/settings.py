"""
Roomies settings.

Everything environment-driven (12-factor). Two profiles fall out naturally:

- Docker / CI: POSTGRES_HOST + REDIS_URL set -> Postgres, Redis cache,
  real Celery broker.
- Bare local dev: nothing set -> SQLite, local-memory cache, Celery runs
  eagerly in-process. `python manage.py runserver` just works.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY", "dev-only-insecure-secret-key-change-in-production"
)
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "daphne",  # ASGI runserver (websockets in dev); must precede staticfiles
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "channels",
    # roomies
    "apps.users",
    "apps.social",
    "apps.rooms",
    "apps.economy",
    "apps.moderation",
]

MIDDLEWARE = [
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database -------------------------------------------------------------

if os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "roomies"),
            "USER": os.getenv("POSTGRES_USER", "roomies"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "roomies"),
            "HOST": os.getenv("POSTGRES_HOST"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Cache ------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "roomies",
        }
    }

# --- Channels (websockets: room chat, presence, WebRTC signaling) -----------

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# --- Celery -----------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = None
# Tasks run synchronously in-process when: no broker is configured (bare
# local dev), or under pytest — a separate worker would write to the dev
# database, not the test database. Must be decided here at import time:
# Celery ignores app.conf mutations once namespaced Django config is loaded.
TESTING = "pytest" in sys.modules
CELERY_TASK_ALWAYS_EAGER = (
    os.getenv("CELERY_TASK_ALWAYS_EAGER", "0") == "1" or not REDIS_URL or TESTING
)
CELERY_TASK_EAGER_PROPAGATES = True

# --- Auth -------------------------------------------------------------------

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# OTP login. In production this would be an SMS provider; in dev mode the
# code is fixed and echoed in the response so the flow is testable without
# one. Documented in the README. Deliberately its own flag (not DEBUG):
# the test runner forces DEBUG=False but still needs the dev OTP flow.
OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "1" if DEBUG else "0") == "1"
DEV_OTP_CODE = os.getenv("DEV_OTP_CODE", "123456")
OTP_TTL_SECONDS = 300

# --- DRF --------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "gifts": "30/min",
        "otp": "5/min",
    },
    "EXCEPTION_HANDLER": "config.exceptions.exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Roomies API",
    "DESCRIPTION": "Live audio-room social backend: rooms, follows, gifting ledger, moderation.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        # two different `status` fields collide on the auto-generated name
        "RoomStatusEnum": [("live", "Live"), ("ended", "Ended")],
        "ReportStatusEnum": [
            ("open", "Open"),
            ("reviewed", "Reviewed"),
            ("actioned", "Actioned"),
        ],
    },
}

# Cache TTL for the live-room list (seconds).
ROOM_LIST_CACHE_TTL = 30

# --- I18N / static ------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The built React app is collected into STATIC_ROOT alongside Django's own
# static files, so one process serves the API, the websockets and the SPA.
_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATICFILES_DIRS = [_FRONTEND_DIST] if _FRONTEND_DIST.is_dir() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
# Render (and any proxy) terminates TLS upstream.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Render injects the public hostname at runtime, so it cannot be baked in.
_RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if _RENDER_HOST:
    ALLOWED_HOSTS.append(_RENDER_HOST)
    CSRF_TRUSTED_ORIGINS.append("https://" + _RENDER_HOST)

# Room recordings are uploaded here. Local disk is fine at this stage; the
# swap to object storage is a one-line DEFAULT_FILE_STORAGE change.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# a mixed room recording, generously bounded
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
