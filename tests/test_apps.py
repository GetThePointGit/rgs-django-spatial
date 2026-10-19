"""AppConfig: het pk-type van de migraties hangt niet van de projectsettings af (#16)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps
from django.db import models

from rgs_django_spatial.models import SpatialMap

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_appconfig_legt_bigautofield_vast():
    config = apps.get_app_config("rgs_django_spatial")
    assert config.default_auto_field == "django.db.models.BigAutoField"
    # SpatialMap is het enige model zonder expliciete pk; de testsettings zetten
    # bewust geen DEFAULT_AUTO_FIELD, dus dit komt uit de AppConfig.
    assert isinstance(SpatialMap._meta.pk, models.BigAutoField)


@pytest.mark.parametrize(
    "settings_module",
    ["testapp.settings_test", "testapp.settings_autofield"],
    ids=["zonder DEFAULT_AUTO_FIELD", "project met AutoField"],
)
def test_makemigrations_check_schoon(settings_module):
    """``makemigrations --check`` is schoon, ongeacht ``DEFAULT_AUTO_FIELD`` van het project.

    In een apart proces, omdat het pk-type bij het laden van de modellen wordt
    bepaald en een ``override_settings`` daar niet meer op ingrijpt.
    """
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "tests"), str(REPO_ROOT)]),
        "DJANGO_SETTINGS_MODULE": settings_module,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "django",
            "makemigrations",
            "--check",
            "--dry-run",
            "--skip-checks",
            "rgs_django_spatial",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No changes detected" in result.stdout
