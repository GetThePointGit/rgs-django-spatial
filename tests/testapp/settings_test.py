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
# Tiles-storage van rgs_django_spatial.tiles.storage: een gewone Django-storage
# onder de alias "tiles" (STORAGES). Tests overschrijven STORAGES waar nodig.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "tiles": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": "/tmp/rgs-django-spatial-tests/tiles",
            "base_url": "/tiles/",
            "allow_overwrite": True,
        },
    },
}
