"""Route-tests: leest en schrijft een gebruiker alleen wat de resolver toestaat."""

import json
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from ninja.testing import TestClient

from rgs_django_spatial.access import SpatialAccess
from rgs_django_spatial.api import router
from rgs_django_spatial.models import SpatialSource
from rgs_django_spatial.models.enums import EnumMapSourceType

client = TestClient(router)

pytestmark = pytest.mark.django_db


def resolver(request):
    data = json.loads(request.META.get("HTTP_X_TOEGANG", "{}"))
    return SpatialAccess(
        lees_org_ids=frozenset(data.get("lees", [])),
        schrijf_org_ids=frozenset(data.get("schrijf", [])),
        schrijf_algemeen=data.get("algemeen", False),
        lees_alles=data.get("lees_alles", False),
        schrijf_alles=data.get("schrijf_alles", False),
    )


def toegang(**kw):
    return {"headers": {"X-TOEGANG": json.dumps(kw)}}


@pytest.fixture
def bronnen(db):
    EnumMapSourceType.objects.get_or_create(id="wms", defaults={"name": "wms"})

    def maak(naam, through="authenticated", access_id=None):
        return SpatialSource.objects.create(
            name=naam,
            source_type_id="wms",
            source_config={"url": "https://x.example/wms", "typename": "l"},
            access_through_id=through,
            access_id=access_id,
            tile_status="klaar",
        )

    return {
        "algemeen": maak("algemeen"),
        "org1": maak("van-1", "organisation", 1),
        "org2": maak("van-2", "organisation", 2),
    }


# --- zonder resolver: huidig gedrag ----------------------------------------------------


def test_zonder_resolver_blijft_alles_open(bronnen):
    with mock.patch("rgs_django_spatial.api.pmtiles_url", return_value="u"):
        resp = client.get("/lagen/")
    assert {r["source_id"] for r in resp.json()} == {b.id for b in bronnen.values()}


# --- lezen -------------------------------------------------------------------------------


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_lagen_alleen_algemeen_en_eigen_org(bronnen):
    with mock.patch("rgs_django_spatial.api.pmtiles_url", return_value="u"):
        resp = client.get("/lagen/", **toegang(lees=[1]))
    assert {r["source_id"] for r in resp.json()} == {bronnen["algemeen"].id, bronnen["org1"].id}


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_velden_van_andere_org_is_404(bronnen):
    resp = client.get(f"/{bronnen['org2'].id}/velden/", **toegang(lees=[1]))
    assert resp.status_code == 404


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_veld_waarden_van_andere_org_is_404(bronnen):
    resp = client.get(f"/{bronnen['org2'].id}/veld-waarden/?veld=x", **toegang(lees=[1]))
    assert resp.status_code == 404


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_geojson_van_andere_org_is_404_ook_als_het_bestand_bestaat(bronnen):
    with mock.patch("rgs_django_spatial.api.read_object", return_value=b"{}") as lees:
        resp = client.get(f"/{bronnen['org2'].id}/geojson/", **toegang(lees=[1]))
        assert resp.status_code == 404
        lees.assert_not_called()
        resp = client.get(f"/{bronnen['org1'].id}/geojson/", **toegang(lees=[1]))
        assert resp.status_code == 200


def test_geojson_zonder_resolver_blijft_zonder_db_check():
    with mock.patch("rgs_django_spatial.api.read_object", return_value=b"{}"):
        assert client.get("/424242/geojson/").status_code == 200


# --- schrijven ---------------------------------------------------------------------------


def _upload(naam="a.geojson"):
    return {"bestand": SimpleUploadedFile(naam, b"{}")}


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
@pytest.mark.parametrize(
    "pad, methode, kwargs",
    [
        ("genereer-tiles", "post", {}),
        ("upload", "post", {"FILES": True}),
        ("upload-geojson", "post", {"FILES": True}),
    ],
)
def test_schrijfroutes_weigeren_lezer_zonder_schrijfrecht(bronnen, pad, methode, kwargs):
    with mock.patch("rgs_django_spatial.api.start_spatial_tile_build") as start:
        extra = {"FILES": _upload()} if kwargs.get("FILES") else {}
        resp = getattr(client, methode)(f"/{bronnen['org1'].id}/{pad}/", **extra, **toegang(lees=[1]))
        assert resp.status_code == 403
        start.assert_not_called()


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
@pytest.mark.parametrize("pad", ["genereer-tiles", "upload", "upload-geojson"])
def test_schrijfroutes_van_andere_org_zijn_404(bronnen, pad):
    extra = {"FILES": _upload()} if pad != "genereer-tiles" else {}
    resp = client.post(f"/{bronnen['org2'].id}/{pad}/", **extra, **toegang(lees=[1], schrijf=[1]))
    assert resp.status_code == 404


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_org_beheerder_mag_eigen_bron_hertegelen(bronnen):
    with (
        mock.patch("rgs_django_spatial.api.gdal_input_for_source"),
        mock.patch("rgs_django_spatial.api.start_spatial_tile_build") as start,
    ):
        resp = client.post(f"/{bronnen['org1'].id}/genereer-tiles/", **toegang(lees=[1], schrijf=[1]))
    assert resp.status_code == 202
    start.assert_called_once_with(bronnen["org1"].id)


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_org_beheerder_mag_algemene_bron_niet_hertegelen(bronnen):
    resp = client.post(f"/{bronnen['algemeen'].id}/genereer-tiles/", **toegang(lees=[1], schrijf=[1]))
    assert resp.status_code == 403


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_staf_mag_algemene_bron_hertegelen(bronnen):
    with (
        mock.patch("rgs_django_spatial.api.gdal_input_for_source"),
        mock.patch("rgs_django_spatial.api.start_spatial_tile_build"),
    ):
        resp = client.post(f"/{bronnen['algemeen'].id}/genereer-tiles/", **toegang(algemeen=True))
    assert resp.status_code == 202


# --- capabilities ------------------------------------------------------------------------

CAP = {"service": "wms", "url": "https://x.example/wms"}


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_capabilities_vereist_schrijfrecht():
    with mock.patch("rgs_django_spatial.api.discover_layers") as ontdek:
        resp = client.post("/capabilities/", json=CAP, **toegang(lees=[1]))
        assert resp.status_code == 403
        ontdek.assert_not_called()


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_capabilities_voor_org_beheerder_en_staf():
    fake = {"service": "wms", "version": "1.3.0", "title": "t", "layers": []}
    with mock.patch("rgs_django_spatial.api.discover_layers", return_value=fake):
        assert client.post("/capabilities/", json=CAP, **toegang(lees=[1], schrijf=[1])).status_code == 200
        assert client.post("/capabilities/", json=CAP, **toegang(algemeen=True)).status_code == 200


def test_capabilities_zonder_resolver_blijft_open():
    fake = {"service": "wms", "version": None, "title": None, "layers": []}
    with mock.patch("rgs_django_spatial.api.discover_layers", return_value=fake):
        assert client.post("/capabilities/", json=CAP).status_code == 200


@override_settings(SPATIAL_ACCESS_RESOLVER="test_api_access.resolver")
def test_staf_leest_en_schrijft_bronnen_van_elke_eigenaar(bronnen):
    staf = toegang(lees_alles=True, schrijf_alles=True)
    with mock.patch("rgs_django_spatial.api.pmtiles_url", return_value="u"):
        assert {r["source_id"] for r in client.get("/lagen/", **staf).json()} == {b.id for b in bronnen.values()}
    with (
        mock.patch("rgs_django_spatial.api.gdal_input_for_source"),
        mock.patch("rgs_django_spatial.api.start_spatial_tile_build"),
    ):
        assert client.post(f"/{bronnen['org2'].id}/genereer-tiles/", **staf).status_code == 202
