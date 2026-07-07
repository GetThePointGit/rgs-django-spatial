"""Pure tests voor de due-selectie van refresh_spatial_tiles (geen DB)."""
from datetime import datetime, timedelta, timezone

from rgs_django_spatial.management.commands.refresh_spatial_tiles import is_due

NOW = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)


def test_alleen_wfs_is_due():
    assert not is_due("geojson", "geen", None, 60, NOW)
    assert is_due("wfs", "geen", None, 60, NOW)


def test_nooit_gebouwd_is_due_ook_zonder_interval():
    assert is_due("wfs", "geen", None, None, NOW)


def test_interval_verstreken():
    oud = NOW - timedelta(minutes=61)
    recent = NOW - timedelta(minutes=10)
    assert is_due("wfs", "klaar", oud, 60, NOW)
    assert not is_due("wfs", "klaar", recent, 60, NOW)


def test_zonder_interval_niet_opnieuw():
    assert not is_due("wfs", "klaar", NOW - timedelta(days=30), None, NOW)


def test_bezig_met_recente_update_is_niet_due():
    recent = NOW - timedelta(minutes=10)
    assert not is_due("wfs", "bezig", recent, 60, NOW)


def test_bezig_stale_is_wel_due():
    # Pod-restart mid-build laat 'bezig' permanent achter; na STALE_BEZIG_MIN
    # (60 min) proberen we opnieuw. Dubbele build is veilig (atomic replace +
    # idempotente output).
    oud = NOW - timedelta(minutes=61)
    assert is_due("wfs", "bezig", oud, 60, NOW)


def test_bezig_zonder_tiles_updated_at_is_due():
    assert is_due("wfs", "bezig", None, 60, NOW)
