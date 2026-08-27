"""
Django local settings for intervenr project.
This is the local settings file, which should NOT be synced
into version control. Sets relevant DB & other settings.
See __init__.py for loading logic.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from intervenr.settings.base import *
import os


# SECURITY WARNING: keep the secret key used in production secret!
# NOTE: DO NOT CHECK INTO GIT VERSION CONTROL!
# Set the SECRET_KEY env var for a real key; otherwise an insecure
# dev-only placeholder is used (never valid for production).

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-dev-only-change-me')


# DEBUG TRUE for local.py development only!

DEBUG = True


# ALLOWED_HOSTS: Add on localhost for local.py

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]


# Database
# NOTE: Set to db.sqlite3 for local.py development.
# See: https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/staticfiles/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static', # just for dev purposes
]

# Python Social Auth
# Set SOCIAL_AUTH_GOOGLE_OAUTH2_KEY / SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET env vars
# to enable Google login locally; left blank, Google login will not work.

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '')

# Python Social Auth (social_django) Settings
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'

SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/onboard/redirect_prolific/'

SOCIAL_AUTH_JSONFIELD_ENABLED = True

SOCIAL_AUTH_URL_NAMESPACE = 'social'

# NOTE: Twitter & FB never set up
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    # 'social_core.backends.twitter.TwitterOAuth',
    # 'social_core.backends.facebook.FacebookOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

# Automated Email
# Set EMAIL_HOST_USER / EMAIL_HOST_PASSWORD env vars to enable outgoing email
# locally; left blank, email sending will not work.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

SOCIAL_AUTH_PIPELINE = [
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.social_user',
    'onboard.pipeline.is_login_attempt_valid',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.social_auth.associate_by_email',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'onboard.pipeline.link_new_account',
]
