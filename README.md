# Intervenr

Research platform + Chrome extension for studying and intervening on users' online media exposure (ads, news), with onboarding and survey data collection.

Built with Django. Study led by researchers at the University of Pennsylvania.

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Runs locally with sensible defaults out of the box. To enable Google login or outgoing email, set:

```
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
```

## Production

Deploys via Heroku (`Procfile`). Configure via environment variables — see `intervenr/settings/production.py` for the full list (`SECRET_KEY`, `DATABASE_*`, `ALLOWED_HOSTS`, etc).