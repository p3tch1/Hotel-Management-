import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'development-only-change-me')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,.vercel.app').split(',') if host.strip()]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'corsheaders', 'rest_framework', 'drf_spectacular', 'hotel']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware']
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request']}}]
# Django's SQL connection is unused. All hotel records and identity data live in MongoDB through hotel.db.
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / '.framework.sqlite3'}}
USE_TZ = True
TIME_ZONE = 'Asia/Kolkata'
LANGUAGE_CODE = 'en-us'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.PBKDF2PasswordHasher']
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',') if origin.strip()]
CORS_ALLOW_HEADERS = ['authorization', 'content-type']
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['hotel.authentication.BearerTokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'hotel.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_RATES': {'anon': '20/minute', 'user': '300/minute', 'login': '5/minute'},
    'EXCEPTION_HANDLER': 'hotel.api.exceptions.api_exception_handler',
}
SPECTACULAR_SETTINGS = {'TITLE': 'Lumen House Hotel API', 'DESCRIPTION': 'Role-protected hotel operations API backed by MongoDB.', 'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False}
JWT_SECRET = os.getenv('JWT_SECRET', SECRET_KEY)
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY', '')
JWT_LIFETIME_SECONDS = int(os.getenv('JWT_LIFETIME_SECONDS', '28800'))
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'hotel_management')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
