"""
Django settings for iot_project.

Multi-tenant Postgres via django-tenants (schema-per-tenant) is the
primary mode. For quick local checks without Postgres, set USE_SQLITE=1
to fall back to a single-schema SQLite database with the tenant layer
short-circuited; this is useful for running unit tests but loses tenant
isolation.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-&gp4#&mji^1%295^nc^2udyjmpsyld3o&nyvv*nj7&b#-_cqzh',
)

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

ALLOWED_HOSTS = ['*']

USE_SQLITE = os.environ.get('USE_SQLITE') == '1'

# --- App layout --------------------------------------------------------
#
# django-tenants splits installed apps into SHARED_APPS (live in the
# public schema, one copy total) and TENANT_APPS (live in each tenant
# schema, one copy per tenant). The full INSTALLED_APPS is the union.

if USE_SQLITE:
    # Single-schema fallback for quick local runs / unit tests.
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'rest_framework',
        'rest_framework.authtoken',
        'devices',
    ]
else:
    SHARED_APPS = [
        'django_tenants',
        'tenants',

        'django.contrib.contenttypes',
        'django.contrib.auth',
        'django.contrib.admin',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'rest_framework',
        'rest_framework.authtoken',
    ]

    TENANT_APPS = [
        'devices',
    ]

    INSTALLED_APPS = SHARED_APPS + [a for a in TENANT_APPS if a not in SHARED_APPS]

    TENANT_MODEL = 'tenants.Tenant'
    TENANT_DOMAIN_MODEL = 'tenants.Domain'

    DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# --- Middleware --------------------------------------------------------
#
# HeaderTenantMiddleware runs before everything else so the DB
# connection is bound to the right schema before any ORM call.
# In SQLite mode we skip it (there's only one schema).

_BASE_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if USE_SQLITE:
    MIDDLEWARE = _BASE_MIDDLEWARE
else:
    MIDDLEWARE = ['tenants.middleware.HeaderTenantMiddleware'] + _BASE_MIDDLEWARE

ROOT_URLCONF = 'iot_project.urls'
if not USE_SQLITE:
    PUBLIC_SCHEMA_URLCONF = 'iot_project.urls_public'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'iot_project.wsgi.application'


# --- Database ----------------------------------------------------------

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django_tenants.postgresql_backend',
            'NAME': os.environ.get('POSTGRES_DB', 'iot_ingestor'),
            'USER': os.environ.get('POSTGRES_USER', 'iot'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'iot'),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
