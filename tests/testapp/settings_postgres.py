"""Settings voor de tests die een echte PostgreSQL nodig hebben.

De gewone suite draait op SQLite (``settings_test``). Daar kan geen
``SpatialLayer`` worden opgeslagen (``ArrayField``) en bestaan geen triggers,
dus de scoperegels van de stijlkoppeling (urbanworks#433) hebben PostgreSQL
nodig::

    pytest --ds=testapp.settings_postgres tests/test_stijl_scope.py

De verbinding komt uit de standaard ``PG*``-omgevingsvariabelen; pytest-django
maakt zelf een wegwerpdatabase ``test_<PGDATABASE>``.
"""

import os

from .settings_test import *  # noqa: F403
from .settings_test import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "django.contrib.postgres"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "spatial"),
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", "postgres"),
        "HOST": os.environ.get("PGHOST", "localhost"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}
