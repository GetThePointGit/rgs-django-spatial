"""Testsettings van een project met ``AutoField`` als standaard (zoals drainworks).

Gebruikt door ``tests/test_apps.py`` om te bewaken dat de migraties niet van
``DEFAULT_AUTO_FIELD`` in de projectsettings afhangen (#16).
"""

from testapp.settings_test import *  # noqa: F403

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
