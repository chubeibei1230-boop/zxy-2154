import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-#zm668*vi95xjftb5wcuo1+l@)dmi4=2vjkufvw9=)w*)@ae^v'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'rest_framework',
    'api',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'recycling_system.urls'

TEMPLATES = []

WSGI_APPLICATION = 'recycling_system.wsgi.application'

DATABASES = {}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.InMemoryTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'EXCEPTION_HANDLER': 'api.exceptions.custom_exception_handler',
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TIME_ZONE = 'Asia/Shanghai'
USE_TZ = True
LANGUAGE_CODE = 'zh-hans'
STATIC_URL = 'static/'

CLEANING_TIMEOUT_HOURS = int(os.environ.get('CLEANING_TIMEOUT_HOURS', 4))
CONFIRMATION_TIMEOUT_HOURS = int(os.environ.get('CONFIRMATION_TIMEOUT_HOURS', 2))
CONTINUOUS_FULL_THRESHOLD = int(os.environ.get('CONTINUOUS_FULL_THRESHOLD', 3))
AREA_ANOMALY_THRESHOLD = int(os.environ.get('AREA_ANOMALY_THRESHOLD', 3))
