"""Tests voor de OWSLib-capabilities-parsers (offline, met stubobjecten)."""

from rgs_django_spatial.tiles.ogc_capabilities import parse_wfs, parse_wms


class _Op:
    """Stub voor een OWSLib-operation (GetMap/GetFeature)."""

    def __init__(self, format_options):
        self.formatOptions = format_options


class _WmsLayer:
    def __init__(self, title, bbox, crs, queryable, abstract=None):
        self.title = title
        self.boundingBoxWGS84 = bbox
        self.crsOptions = crs
        self.queryable = queryable
        self.abstract = abstract


class _WmsStub:
    """Stub met .contents en .getOperationByName, zoals OWSLib WebMapService."""

    def __init__(self, contents, formats):
        self.contents = contents
        self._formats = formats

    def getOperationByName(self, name):
        return _Op(self._formats)


class _WfsFeatureType:
    def __init__(self, title, bbox, crs, abstract=None):
        self.title = title
        self.boundingBoxWGS84 = bbox
        self.crsOptions = crs
        self.abstract = abstract


class _WfsStub:
    def __init__(self, contents):
        self.contents = contents


def test_parse_wms_mapt_named_layers():
    wms = _WmsStub(
        contents={
            "": _WmsLayer("Groep", None, [], 0),  # groep zonder name → overslaan
            "roads": _WmsLayer("Wegen", (3.0, 50.0, 7.5, 54.0), ["EPSG:3857", "EPSG:4326"], 1, "abstract-tekst"),
        },
        formats=["image/png", "image/jpeg"],
    )
    out = parse_wms(wms)
    assert len(out) == 1
    laag = out[0]
    assert laag["name"] == "roads"
    assert laag["title"] == "Wegen"
    assert laag["abstract"] == "abstract-tekst"
    assert laag["bbox_wgs84"] == [3.0, 50.0, 7.5, 54.0]
    assert laag["crs"] == ["EPSG:3857", "EPSG:4326"]
    assert laag["formats"] == ["image/png", "image/jpeg"]
    assert laag["queryable"] is True
    assert laag["geometry_type"] is None


def test_parse_wfs_mapt_feature_types():
    wfs = _WfsStub(
        contents={
            "ns:panden": _WfsFeatureType("Panden", (3.0, 50.0, 7.5, 54.0), ["urn:ogc:def:crs:EPSG::28992"]),
        }
    )
    out = parse_wfs(wfs)
    assert len(out) == 1
    laag = out[0]
    assert laag["name"] == "ns:panden"
    assert laag["title"] == "Panden"
    assert laag["bbox_wgs84"] == [3.0, 50.0, 7.5, 54.0]
    assert laag["crs"] == ["urn:ogc:def:crs:EPSG::28992"]
    assert laag["queryable"] is None
    assert laag["geometry_type"] is None
