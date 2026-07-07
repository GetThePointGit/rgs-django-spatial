"""Tiles storage backend selection + key building are pure/local-testable.

S3 upload + presign are covered by an integration test gated on real creds;
here we only assert the pure key/path-building helpers, using monkeypatch
against ``django.conf.settings`` (this project does not use pytest-django).
"""
import os

from django.conf import settings as dj_settings

from rgs_django_spatial.tiles import storage


def test_tiles_key_without_prefix():
    assert storage._tiles_key("42.pmtiles") == "42.pmtiles"


def test_tiles_key_with_prefix_is_normalised():
    assert storage._tiles_key("42.pmtiles", "/tiles/") == "tiles/42.pmtiles"


def test_local_pmtiles_url_is_stable_path(monkeypatch):
    # TILES_STORAGE is not defined on settings yet (Task 7 adds it), so this
    # attribute may not exist -- allow setattr to create it.
    monkeypatch.setattr(dj_settings, "TILES_STORAGE", "local", raising=False)
    assert storage.pmtiles_url("7.pmtiles") == "/tiles/7.pmtiles"


def test_local_pmtiles_path_supports_subdir(monkeypatch, tmp_path):
    from django.conf import settings
    from rgs_django_spatial.tiles.storage import local_pmtiles_path
    monkeypatch.setattr(settings, "VAR_DIR", str(tmp_path), raising=False)
    assert local_pmtiles_path("spatial/7.pmtiles") == str(tmp_path / "tiles" / "spatial" / "7.pmtiles")


def test_store_pmtiles_local_moves_file(monkeypatch, tmp_path):
    monkeypatch.setattr(dj_settings, "TILES_STORAGE", "local", raising=False)
    monkeypatch.setattr(dj_settings, "VAR_DIR", str(tmp_path))
    src = tmp_path / "src.pmtiles"
    src.write_bytes(b"PMTILESDATA")
    storage.store_pmtiles("99.pmtiles", str(src))
    dst = tmp_path / "tiles" / "99.pmtiles"
    assert dst.read_bytes() == b"PMTILESDATA"
    assert not src.exists()  # moved, not copied


def test_store_pmtiles_local_creates_subdirs(monkeypatch, tmp_path):
    from django.conf import settings
    from rgs_django_spatial.tiles.storage import store_pmtiles, local_pmtiles_path
    monkeypatch.setattr(settings, "VAR_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "TILES_STORAGE", "local", raising=False)
    src = tmp_path / "in.pmtiles"
    src.write_bytes(b"x")
    store_pmtiles("spatial/7.pmtiles", str(src))
    assert os.path.exists(local_pmtiles_path("spatial/7.pmtiles"))


def test_s3_object_path_builds_bucket_and_key(monkeypatch):
    # TILES_S3 is not defined on settings yet (Task 7 adds it), so allow
    # setattr to create it rather than requiring it to pre-exist.
    monkeypatch.setattr(
        dj_settings,
        "TILES_S3",
        {
            "bucket": "urbanworks-tiles",
            "prefix": "pmtiles",
            "key": "AKIA...",
            "secret": "...",
            "endpoint_url": "https://s3.nl-ams.scw.cloud",
        },
        raising=False,
    )
    assert storage._s3_object_path("123.pmtiles") == "urbanworks-tiles/pmtiles/123.pmtiles"


def test_delete_pmtiles_local_removes_file(monkeypatch, tmp_path):
    from django.conf import settings as dj_settings
    from rgs_django_spatial.tiles import storage
    monkeypatch.setattr(dj_settings, "TILES_STORAGE", "local", raising=False)
    monkeypatch.setattr(dj_settings, "VAR_DIR", str(tmp_path), raising=False)
    dst = tmp_path / "tiles" / "5.pmtiles"
    dst.parent.mkdir(parents=True)
    dst.write_bytes(b"X")
    storage.delete_pmtiles("5.pmtiles")
    assert not dst.exists()


def test_delete_pmtiles_local_missing_is_noop(monkeypatch, tmp_path):
    from django.conf import settings as dj_settings
    from rgs_django_spatial.tiles import storage
    monkeypatch.setattr(dj_settings, "TILES_STORAGE", "local", raising=False)
    monkeypatch.setattr(dj_settings, "VAR_DIR", str(tmp_path), raising=False)
    storage.delete_pmtiles("999.pmtiles")  # must not raise


def test_settings_expose_tiles_storage_default_local():
    from django.conf import settings
    assert getattr(settings, "TILES_STORAGE", "local") == "local"
