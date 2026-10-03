"""Tests voor de pluggable toegangsregeling (algemeen of van één eigenaar)."""

import json

import pytest
from django.http import HttpRequest
from django.test import override_settings

from rgs_django_spatial.access import SpatialAccess, get_access


class Rij:
    """Stub met alleen de scopekolommen."""

    def __init__(self, through, access_id=None):
        self.access_through_id = through
        self.access_id = access_id


ALGEMEEN = Rij("authenticated")
ORG_1 = Rij("organisation", 1)
ORG_2 = Rij("organisation", 2)
ANDERS = Rij("user", 5)


def test_lezen_algemeen_en_eigen_org():
    toegang = SpatialAccess(lees_org_ids=frozenset({1}))
    assert toegang.mag_lezen(ALGEMEEN)
    assert toegang.mag_lezen(ORG_1)
    assert not toegang.mag_lezen(ORG_2)


def test_andere_scopesoorten_zijn_nooit_leesbaar():
    assert not SpatialAccess(lees_org_ids=frozenset({5}), schrijf_algemeen=True).mag_lezen(ANDERS)


def test_schrijven_eigen_org_niet_algemeen():
    toegang = SpatialAccess(lees_org_ids=frozenset({1}), schrijf_org_ids=frozenset({1}))
    assert toegang.mag_schrijven(ORG_1)
    assert not toegang.mag_schrijven(ORG_2)
    assert not toegang.mag_schrijven(ALGEMEEN)


def test_staf_schrijft_algemeen():
    toegang = SpatialAccess(schrijf_algemeen=True)
    assert toegang.mag_schrijven(ALGEMEEN)
    assert not toegang.mag_schrijven(ORG_1)


def test_schrijven_vereist_ook_lezen_van_dezelfde_rij():
    # schrijf-org zonder lees-org: de rij blijft onleesbaar, dus ook niet schrijfbaar.
    toegang = SpatialAccess(schrijf_org_ids=frozenset({1}))
    assert not toegang.mag_schrijven(ORG_1)


def test_lees_alles_ziet_ook_andere_scopesoorten_en_eigenaars():
    toegang = SpatialAccess(lees_alles=True)
    for rij in (ALGEMEEN, ORG_1, ORG_2, ANDERS):
        assert toegang.mag_lezen(rij)


def test_schrijf_alles_schrijft_overal_waar_het_leest():
    toegang = SpatialAccess(lees_alles=True, schrijf_alles=True)
    for rij in (ALGEMEEN, ORG_1, ORG_2):
        assert toegang.mag_schrijven(rij)
    assert toegang.kan_schrijven()
    assert not SpatialAccess(schrijf_alles=True).mag_schrijven(ORG_1)  # onleesbaar blijft onschrijfbaar


def test_kan_schrijven():
    assert not SpatialAccess().kan_schrijven()
    assert SpatialAccess(schrijf_algemeen=True).kan_schrijven()
    assert SpatialAccess(schrijf_org_ids=frozenset({3})).kan_schrijven()


def _resolver(request):
    data = json.loads(request.META.get("HTTP_X_TOEGANG", "{}"))
    return SpatialAccess(
        lees_org_ids=frozenset(data.get("lees", [])),
        schrijf_org_ids=frozenset(data.get("schrijf", [])),
        schrijf_algemeen=data.get("algemeen", False),
    )


def test_get_access_zonder_resolver_is_onbeperkt():
    assert get_access(HttpRequest()) is None


@override_settings(SPATIAL_ACCESS_RESOLVER="test_access._resolver")
def test_get_access_roept_de_resolver_aan():
    request = HttpRequest()
    request.META["HTTP_X_TOEGANG"] = json.dumps({"lees": [4]})
    assert get_access(request) == SpatialAccess(lees_org_ids=frozenset({4}))


@override_settings(SPATIAL_ACCESS_RESOLVER="bestaat.niet.functie")
def test_get_access_met_kapotte_resolver_faalt_luid():
    with pytest.raises(ImportError):
        get_access(HttpRequest())


@override_settings(SPATIAL_ACCESS_RESOLVER="test_access._telresolver")
def test_get_access_roept_de_resolver_maar_een_keer_per_verzoek_aan():
    _AANROEPEN.clear()
    request = HttpRequest()
    eerste = get_access(request)
    assert get_access(request) is eerste
    assert len(_AANROEPEN) == 1
    # Een ander verzoek krijgt een eigen resolutie.
    get_access(HttpRequest())
    assert len(_AANROEPEN) == 2


_AANROEPEN: list = []


def _telresolver(request):
    _AANROEPEN.append(request)
    return SpatialAccess()
