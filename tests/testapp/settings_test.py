"""Minimale Django-settings voor de pure pakket-tests (geen echte DB)."""

SECRET_KEY = "test-only"
USE_TZ = True
# Bewust géén DEFAULT_AUTO_FIELD: de app legt het pk-type zelf vast via
# ``default_auto_field`` op de AppConfig (#16). Zie ook settings_autofield.py.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rgs_django_utils",
    "rgs_django_spatial",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
# Settings-contract van rgs_django_spatial.tiles (zie storage.py); tests
# monkeypatchen deze waar nodig.
VAR_DIR = "/tmp/rgs-django-spatial-tests"
TILES_STORAGE = "local"
