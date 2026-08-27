"""
Django root settings module for intervenr project.
This file auto executes when django first loads settings in,
and will load either local.py or production.py depending on 
environment variables. Both of these themselves import base.py, which
shares settings across both files.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import os

if 'DJANGO_PRODUCTION' in os.environ:
    from intervenr.settings.production import *
else:
    from intervenr.settings.local import *