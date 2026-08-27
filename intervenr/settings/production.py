"""
Django production settings for intervenr project.
This is the production settings file, which SHOULD be synced
into version control. Sets relevant DB & other settings.
See __init__.py for loading logic.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""
from intervenr.settings.base import *
import os


# SECURITY WARNING: For security purposes, this secret key is not checked into
# production, and is only accessible as an environment variable.
SECRET_KEY = os.environ['SECRET_KEY']

# Security Settings, prefer SSL
SECURE_SSL_REDIRECT = True


# DEBUG is FALSE for production.py official server!
DEBUG = False


# ALLOWED_HOSTS: set via a comma-separated ALLOWED_HOSTS env var, e.g.
# "myapp.herokuapp.com,myapp.example.edu".
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')


# Database
# NOTE: Update this to official database once production migrated over.
# All of these values are set in the Heroku environment variables page.
# These environment variables contain all of the information needed to configure
# and setup the postgresql server for the production server when deployed.
# See: https://docs.djangoproject.com/en/3.1/ref/settings/#databases
#      https://medium.com/swlh/creating-a-postgresql-db-on-aws-and-connecting-it-to-heroku-django-app-29603df20c2a
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DATABASE_NAME'],
        'USER': os.environ['DATABASE_USER'],
        'PASSWORD': os.environ['DATABASE_PASSWORD'],
        'HOST': os.environ['DATABASE_HOST'],
        'PORT': os.environ['DATABASE_PORT'],
    }
}

# NOTE: The lines below actually setup the right url connection, make sure to setup correctly too.
import dj_database_url
db_from_env = dj_database_url.config(conn_max_age=600)
DATABASES['default'].update(db_from_env)

# Static files (CSS, JavaScript, Images)
# Django Settings: https://docs.djangoproject.com/en/3.1/howto/static-files/deployment/
#                  https://docs.djangoproject.com/en/3.1/howto/static-files/
# Guide: https://testdriven.io/blog/storing-django-static-and-media-files-on-amazon-s3/
#        https://stackabuse.com/serving-static-files-in-python-with-django-aws-s3-and-whitenoise/
# Documentation: https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html

# NOTE: AWS setup currently not working, need to try debugging
# NOTE NOTE: WE ARE NO LONGER USING AWS FOR STATIC FILE STORAGE.
# AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
# AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
# AWS_STORAGE_BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']
# AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
# AWS_LOCATION = 'static'
# STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/'
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

STATIC_URL = '/staticfiles/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Python Social Auth
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ['GOOGLE_PLUS_KEY']
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ['GOOGLE_PLUS_SECRET']

# Automated Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
