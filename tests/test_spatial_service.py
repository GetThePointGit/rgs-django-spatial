"""Pure tests voor de spatial-tilepijplijn (geen database)."""
from osgeo import gdal

from rgs_django_spatial.tiles.spatial_service import gdal_auth_config, gdal_input_for_source, spatial_tiles_key


class FakeSource:
    def __init__(self, source_type_id, source_config=None, file=None):
        self.id = 7
        self.source_type_id = source_type_id
        self.source_config = source_config or {}
        self.file = file


class FakeAuthSource:
    """Stub-bron met auth-velden voor gdal_auth_config."""
    def __init__(self, source_type_id, source_config, auth_type=None, auth_config=None):
        self.source_type_id = source_type_id
        self.source_config = source_config
        self.file = None
        self.authentication_type_id = auth_type
        self.authentication_config = auth_config


def test_spatial_tiles_key():
    assert spatial_tiles_key(7) == "spatial/7.pmtiles"


def test_gdal_input_wfs_bouwt_wfs_url():
    src = FakeSource("wfs", {"url": "https://example.com/wfs", "typename": "ns:laag"})
    ctx, layer = gdal_input_for_source(src)
    with ctx as path:
        assert path == "WFS:https://example.com/wfs"
    assert layer == "ns:laag"


def test_gdal_input_wfs_zonder_url_faalt():
    import pytest
    src = FakeSource("wfs", {})
    with pytest.raises(ValueError):
        gdal_input_for_source(src)


def test_gdal_input_bestand_zonder_file_faalt():
    import pytest
    src = FakeSource("geojson", {}, file=None)
    with pytest.raises(ValueError):
        gdal_input_for_source(src)


def test_gdal_input_geojson_url_geeft_vsicurl():
    src = FakeAuthSource("geojson", {"data": "https://example.com/data.geojson"})
    ctx, layer = gdal_input_for_source(src)
    with ctx as path:
        assert path == "/vsicurl/https://example.com/data.geojson"
    assert layer is None


def test_gdal_input_geojson_lokaal_valt_terug_op_bestand():
    # data die géén http(s) is (geserveerde geojson) → geen /vsicurl, en zonder
    # file een nette ValueError.
    src = FakeAuthSource("geojson", {"data": "/api/spatial/5/geojson"})
    try:
        gdal_input_for_source(src)
        assert False, "verwachtte ValueError"
    except ValueError:
        pass


def test_gdal_auth_config_zet_en_herstelt_userpwd():
    src = FakeAuthSource("wfs", {"url": "x"}, auth_type="basic_auth",
                         auth_config={"username": "u", "password": "p"})
    assert gdal.GetThreadLocalConfigOption("GDAL_HTTP_USERPWD") is None
    with gdal_auth_config(src):
        assert gdal.GetThreadLocalConfigOption("GDAL_HTTP_USERPWD") == "u:p"
    assert gdal.GetThreadLocalConfigOption("GDAL_HTTP_USERPWD") is None


def test_gdal_auth_config_no_op_zonder_auth():
    src = FakeAuthSource("wfs", {"url": "x"})
    with gdal_auth_config(src):
        assert gdal.GetThreadLocalConfigOption("GDAL_HTTP_USERPWD") is None
