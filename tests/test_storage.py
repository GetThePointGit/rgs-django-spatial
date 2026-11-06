"""``rgs_django_spatial.tiles.storage`` praat alleen via de Django-storage-API.

Lokaal met ``FileSystemStorage`` (uit ``settings_test``), presign met stub-storages
die ``url_signed`` wel of niet kunnen, en de overgangsroute met de oude
``TILES_*``-settings via ``django_fsspec.FsspecStorage``.
"""

import warnings

import pytest
from django.core.exceptions import ImproperlyConfigured
from testapp import tiles_stubs

from rgs_django_spatial.tiles import storage

FS = "django.core.files.storage.FileSystemStorage"


def _storages_met_tiles(tmp_path, **opties):
    return {
        "default": {"BACKEND": FS},
        "tiles": {
            "BACKEND": FS,
            "OPTIONS": {"location": str(tmp_path / "tiles"), "base_url": "/tiles/", "allow_overwrite": True, **opties},
        },
    }


@pytest.fixture
def tiles_dir(settings, tmp_path):
    settings.STORAGES = _storages_met_tiles(tmp_path)
    return tmp_path / "tiles"


def _bron(tmp_path, inhoud=b"PMTILESDATA"):
    src = tmp_path / "bron.pmtiles"
    src.write_bytes(inhoud)
    return src


# ---------- lokaal (FileSystemStorage) ----------


def test_store_pmtiles_saves_under_key_and_removes_source(tiles_dir, tmp_path):
    src = _bron(tmp_path)
    storage.store_pmtiles("99.pmtiles", str(src))
    assert (tiles_dir / "99.pmtiles").read_bytes() == b"PMTILESDATA"
    assert not src.exists()


def test_store_pmtiles_creates_subdirs(tiles_dir, tmp_path):
    storage.store_pmtiles("spatial/7.pmtiles", str(_bron(tmp_path, b"x")))
    assert (tiles_dir / "spatial" / "7.pmtiles").read_bytes() == b"x"


def test_store_pmtiles_overwrites_existing(tiles_dir, tmp_path):
    storage.store_pmtiles("7.pmtiles", str(_bron(tmp_path, b"oud")))
    storage.store_pmtiles("7.pmtiles", str(_bron(tmp_path, b"nieuw")))
    assert (tiles_dir / "7.pmtiles").read_bytes() == b"nieuw"
    assert sorted(p.name for p in tiles_dir.iterdir()) == ["7.pmtiles"]


def test_store_pmtiles_rejects_storage_that_renames(settings, tmp_path):
    settings.STORAGES = _storages_met_tiles(tmp_path, allow_overwrite=False)
    storage.store_pmtiles("7.pmtiles", str(_bron(tmp_path, b"oud")))
    with pytest.raises(ImproperlyConfigured, match="overschrijven"):
        storage.store_pmtiles("7.pmtiles", str(_bron(tmp_path, b"nieuw")))
    # Het hernoemde object is weer opgeruimd; het origineel staat er nog.
    assert sorted(p.name for p in (tmp_path / "tiles").iterdir()) == ["7.pmtiles"]
    assert (tmp_path / "tiles" / "7.pmtiles").read_bytes() == b"oud"


def test_delete_pmtiles_removes_file_and_is_idempotent(tiles_dir, tmp_path):
    storage.store_pmtiles("5.pmtiles", str(_bron(tmp_path)))
    storage.delete_pmtiles("5.pmtiles")
    assert not (tiles_dir / "5.pmtiles").exists()
    storage.delete_pmtiles("5.pmtiles")  # mag niet gooien


def test_read_object_returns_bytes(tiles_dir, tmp_path):
    storage.store_pmtiles("spatial/3.geojson", str(_bron(tmp_path, b"{}")))
    assert storage.read_object("spatial/3.geojson") == b"{}"


def test_read_object_missing_raises_file_not_found(tiles_dir):
    with pytest.raises(FileNotFoundError):
        storage.read_object("bestaat-niet.geojson")


def test_pmtiles_url_local_uses_storage_url(tiles_dir):
    assert storage.pmtiles_url("7.pmtiles") == "/tiles/7.pmtiles"


# ---------- presign (duck-typed url_signed) ----------


def test_pmtiles_url_prefers_url_signed_with_ttl(settings):
    settings.STORAGES = {"default": {"BACKEND": FS}, "tiles": {"BACKEND": "testapp.tiles_stubs.SignedStubStorage"}}
    settings.TILES_URL_TTL = 1234
    tiles_stubs.SIGNED_CALLS.clear()
    assert storage.pmtiles_url("7.pmtiles") == "https://signed.example/7.pmtiles?ttl=1234"
    assert tiles_stubs.SIGNED_CALLS == [("7.pmtiles", 1234)]


def test_pmtiles_url_default_ttl_is_24h(settings):
    settings.STORAGES = {"default": {"BACKEND": FS}, "tiles": {"BACKEND": "testapp.tiles_stubs.SignedStubStorage"}}
    tiles_stubs.SIGNED_CALLS.clear()
    storage.pmtiles_url("7.pmtiles")
    assert tiles_stubs.SIGNED_CALLS == [("7.pmtiles", 86400)]


def test_pmtiles_url_falls_back_when_url_signed_not_implemented(settings):
    settings.STORAGES = {"default": {"BACKEND": FS}, "tiles": {"BACKEND": "testapp.tiles_stubs.UnsignedStubStorage"}}
    assert storage.pmtiles_url("7.pmtiles") == "/plain/7.pmtiles"


def test_custom_alias(settings):
    settings.STORAGES = {"default": {"BACKEND": FS}, "kaart": {"BACKEND": "testapp.tiles_stubs.SignedStubStorage"}}
    settings.SPATIAL_TILES_STORAGE_ALIAS = "kaart"
    assert storage.pmtiles_url("1.pmtiles").startswith("https://signed.example/1.pmtiles")


def test_missing_alias_without_legacy_settings_is_improperly_configured(settings):
    settings.STORAGES = {"default": {"BACKEND": FS}}
    for naam in ("TILES_STORAGE", "TILES_S3"):
        if hasattr(settings, naam):
            delattr(settings, naam)
    with pytest.raises(ImproperlyConfigured, match="'tiles'"):
        storage.tiles_storage()


# ---------- overgangsroute: oude TILES_*-settings ----------


def test_legacy_local_settings_build_fsspec_storage_with_warning(settings, tmp_path):
    settings.STORAGES = {"default": {"BACKEND": FS}}
    settings.TILES_STORAGE = "local"
    settings.VAR_DIR = str(tmp_path)
    with pytest.warns(DeprecationWarning, match="STORAGES"):
        storage.store_pmtiles("spatial/7.pmtiles", str(_bron(tmp_path, b"legacy")))
    assert (tmp_path / "tiles" / "spatial" / "7.pmtiles").read_bytes() == b"legacy"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert storage.pmtiles_url("spatial/7.pmtiles") == "/tiles/spatial/7.pmtiles"
        assert storage.read_object("spatial/7.pmtiles") == b"legacy"
        storage.delete_pmtiles("spatial/7.pmtiles")
    assert not (tmp_path / "tiles" / "spatial" / "7.pmtiles").exists()


def test_legacy_s3_settings_map_bucket_and_prefix(settings):
    from django_fsspec import FsspecStorage

    settings.STORAGES = {"default": {"BACKEND": FS}}
    settings.TILES_STORAGE = "s3"
    settings.TILES_S3 = {
        "key": "AKIA...",
        "secret": "...",
        "endpoint_url": "https://s3.nl-ams.scw.cloud",
        "bucket": "urbanworks-tiles",
        "prefix": "/pmtiles/",
        "region": "nl-ams",
    }
    with pytest.warns(DeprecationWarning):
        st = storage.tiles_storage()
    assert isinstance(st, FsspecStorage)
    assert st.on_collision == "overwrite"
    s3_fs, bucket, key = st._resolve_s3_target("123.pmtiles")
    assert (bucket, key) == ("urbanworks-tiles", "pmtiles/123.pmtiles")
    assert s3_fs.client_kwargs == {"region_name": "nl-ams"}
    assert hasattr(st, "url_signed")
