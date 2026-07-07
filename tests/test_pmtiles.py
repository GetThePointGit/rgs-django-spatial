import json
import os
import tempfile

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from rgs_django_spatial.tiles.pmtiles import distinct_veldwaarden, generate_pmtiles, inspect_layers, inspect_vector


def _make_gpkg(path: str):
    # Klein vlak in RD New (EPSG:28992), zoals NL-data
    poly = Polygon([(200000, 440000), (200100, 440000), (200100, 440100), (200000, 440100)])
    gdf = gpd.GeoDataFrame({"naam": ["cel1"]}, geometry=[poly], crs="EPSG:28992")
    gdf.to_file(path, layer="hexlaag", driver="GPKG")


def test_inspect_vector_reports_layer_geom_and_wgs84_extent():
    d = tempfile.mkdtemp()
    gpkg = os.path.join(d, "t.gpkg")
    _make_gpkg(gpkg)
    info = inspect_vector(gpkg)
    assert info.layer_name == "hexlaag"
    assert info.geometry_type == "polygon"
    assert info.feature_count == 1
    # RD New rond Gelderland → ~lon 6.x, lat 51.x na transform naar WGS84
    assert 5.5 < info.extent[0] < 7.0
    assert 51.0 < info.extent[1] < 52.5


def test_generate_pmtiles_creates_nonempty_file():
    d = tempfile.mkdtemp()
    gpkg = os.path.join(d, "t.gpkg")
    _make_gpkg(gpkg)
    out = os.path.join(d, "tiles", "1.pmtiles")
    generate_pmtiles(gpkg, out, minzoom=0, maxzoom=10)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def _schrijf_geojson(features: list[dict]) -> str:
    fd, pad = tempfile.mkstemp(suffix=".geojson")
    with os.fdopen(fd, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    return pad


def _punt(soort) -> dict:
    return {"type": "Feature", "properties": {"soort": soort},
            "geometry": {"type": "Point", "coordinates": [5.0, 52.0]}}


def test_inspect_layers_geeft_veldnamen():
    pad = _schrijf_geojson([_punt("eik")])
    try:
        lagen = inspect_layers(pad)
        assert lagen[0]["fields"] == ["soort"]
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_geeft_unieke_waarden():
    pad = _schrijf_geojson([_punt("eik"), _punt("beuk"), _punt("eik")])
    try:
        waarden, afgekapt = distinct_veldwaarden(pad, "soort")
        assert sorted(map(str, waarden)) == ["beuk", "eik"]
        assert afgekapt is False
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_capt_op_limiet():
    pad = _schrijf_geojson([_punt(f"s{i}") for i in range(25)])
    try:
        waarden, afgekapt = distinct_veldwaarden(pad, "soort", limiet=20)
        assert len(waarden) == 20
        assert afgekapt is True
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_onbekend_veld():
    pad = _schrijf_geojson([_punt("eik")])
    try:
        with pytest.raises(ValueError):
            distinct_veldwaarden(pad, "bestaat_niet")
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_onleesbare_bron():
    fd, pad = tempfile.mkstemp(suffix=".geojson")
    with os.fdopen(fd, "w") as f:
        f.write("dit is geen geldige geojson")
    try:
        with pytest.raises(ValueError):
            distinct_veldwaarden(pad, "x")
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_onbekende_laag():
    pad = _schrijf_geojson([_punt("eik")])
    try:
        with pytest.raises(ValueError):
            distinct_veldwaarden(pad, "soort", laag="bestaat_niet")
    finally:
        os.remove(pad)


def test_distinct_veldwaarden_max_features_capt_scan(tmp_path):
    import json
    p = tmp_path / "veel.geojson"
    features = [
        {"type": "Feature", "properties": {"k": f"v{i}"},
         "geometry": {"type": "Point", "coordinates": [i, i]}}
        for i in range(5)
    ]
    p.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    from rgs_django_spatial.tiles.pmtiles import distinct_veldwaarden
    # Zonder cap: 5 unieke waarden (afgekapt False want < limiet 20).
    waarden, afgekapt = distinct_veldwaarden(str(p), "k")
    assert set(waarden) == {"v0", "v1", "v2", "v3", "v4"}
    # Met cap op 2 features: alleen de eerste 2 worden gescand.
    waarden2, _ = distinct_veldwaarden(str(p), "k", max_features=2)
    assert len(waarden2) == 2
