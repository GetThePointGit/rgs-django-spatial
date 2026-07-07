"""Pure tests voor de default_style→stijlrecord-migratielogica (geen DB)."""
from rgs_django_spatial.management.commands.migrate_default_styles import wil_migreren


def test_migreert_alleen_met_style_en_zonder_records():
    style = {"type": "line", "paint": {"line-color": "red"}}
    assert wil_migreren(style, 0)
    assert not wil_migreren(style, 1)      # al stijlrecords → overslaan
    assert not wil_migreren(None, 0)       # niets te migreren
    assert not wil_migreren({}, 0)
