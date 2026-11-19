"""Scope van stijlen, kleurensets en stijlkoppelingen (urbanworks#433).

De regels van ``SpatialLayerStyle`` (scope volgt een organisatielaag, ``vervangt``,
``standaard``), de scope-toewijzing van migratie 0011 en het meenemen van stijlen
bij ``upgrade_laag_naar_applicatiebreed``.

De tests met een laag hebben PostgreSQL nodig (``SpatialLayer`` heeft een
``ArrayField`` en de trigger ``spatial_layer_style_scope`` bestaat alleen daar);
op de SQLite-settings worden ze overgeslagen. Draaien::

    pytest --ds=testapp.settings_postgres tests/test_stijl_scope.py
"""

import importlib

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from rgs_django_spatial.applicatiebreed import kleurenset_ids, upgrade_laag_naar_applicatiebreed
from rgs_django_spatial.models import (
    SpatialKleurenset,
    SpatialLayer,
    SpatialLayerStyle,
    SpatialSource,
    SpatialStyle,
)
from rgs_django_spatial.models.enums import EnumMapSourceType

pytestmark = pytest.mark.django_db

ALGEMEEN = {"access_through_id": "authenticated", "access_id": None}
migratie = importlib.import_module("rgs_django_spatial.migrations.0011_stijl_scope")


def org(org_id: int) -> dict:
    return {"access_through_id": "organisation", "access_id": org_id}


def scope(rij) -> tuple:
    rij.refresh_from_db()
    return (rij.access_through_id, rij.access_id)


@pytest.fixture
def maak_laag(db):
    if connection.vendor != "postgresql":
        pytest.skip("heeft PostgreSQL nodig (--ds=testapp.settings_postgres)")
    EnumMapSourceType.objects.get_or_create(id="wms", defaults={"name": "wms"})

    def maak(naam, **scope_velden):
        bron = SpatialSource.objects.create(
            name=f"bron {naam}", source_type_id="wms", source_config={}, tile_status="klaar", **scope_velden
        )
        return SpatialLayer.objects.create(name=naam, source=bron, **scope_velden)

    return maak


def maak_stijl(naam="stijl", config=None, **scope_velden):
    return SpatialStyle.objects.create(name=naam, style_config=config or {"versie": 3}, **scope_velden)


def koppel(laag, stijl, **velden):
    velden.setdefault("name", stijl.name)
    velden.setdefault("order", 1)
    return SpatialLayerStyle.objects.create(layer=laag, style=stijl, **velden)


# --- scope van de koppelrij ----------------------------------------------------------


def test_koppelrij_op_een_organisatielaag_volgt_de_laag(maak_laag):
    laag = maak_laag("van-1", **org(1))
    rij = koppel(laag, maak_stijl())
    assert scope(rij) == ("organisation", 1)


def test_koppelrij_op_een_applicatiebrede_laag_houdt_haar_eigen_scope(maak_laag):
    laag = maak_laag("algemeen")
    assert scope(koppel(laag, maak_stijl("a"))) == ("authenticated", None)
    assert scope(koppel(laag, maak_stijl("b", **org(1)), **org(1))) == ("organisation", 1)


def test_organisatierij_zonder_organisatie_id_wordt_geweigerd(maak_laag):
    with pytest.raises(ValidationError) as fout:
        koppel(maak_laag("algemeen"), maak_stijl(), access_through_id="organisation")
    assert "access_id" in fout.value.message_dict


def test_stijl_van_een_andere_organisatie_wordt_geweigerd(maak_laag):
    laag = maak_laag("algemeen")
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl(**org(2)), **org(1))
    assert "style" in fout.value.message_dict
    # Ook een applicatiebrede koppelrij mag geen organisatiestijl dragen.
    with pytest.raises(ValidationError):
        koppel(laag, maak_stijl("x", **org(2)))


def test_dezelfde_stijl_mag_per_scope_een_keer(maak_laag):
    laag = maak_laag("algemeen")
    stijl = maak_stijl()
    koppel(laag, stijl)
    koppel(laag, stijl, **org(1))
    koppel(laag, stijl, **org(2))
    with pytest.raises(IntegrityError), transaction.atomic():
        koppel(laag, stijl, **org(1))


# --- vervangt ------------------------------------------------------------------------


def test_organisatie_vervangt_een_standaardrij(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    variant = koppel(laag, maak_stijl("Status (eigen)", **org(1)), vervangt=standaardrij, **org(1))
    assert list(standaardrij.vervangers.all()) == [variant]


def test_een_variant_per_standaardrij_per_organisatie(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    koppel(laag, maak_stijl("a", **org(1)), vervangt=standaardrij, **org(1))
    koppel(laag, maak_stijl("b", **org(2)), vervangt=standaardrij, **org(2))
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl("c", **org(1)), vervangt=standaardrij, **org(1))
    assert "vervangt" in fout.value.message_dict


def test_een_tweede_variant_botst_ook_op_de_constraint(maak_laag):
    """Zonder ``save()`` (bulk_create, zoals Hasura) vangt de unieke index het af."""
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    koppel(laag, maak_stijl("a", **org(1)), vervangt=standaardrij, **org(1))
    dubbel = SpatialLayerStyle(
        layer=laag, style=maak_stijl("b", **org(1)), name="b", order=2, vervangt=standaardrij, **org(1)
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        SpatialLayerStyle.objects.bulk_create([dubbel])


def test_applicatiebrede_rij_kan_niets_vervangen(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl("x"), vervangt=standaardrij)
    assert "vervangt" in fout.value.message_dict
    # En de check-constraint voor wie save() omzeilt.
    rij = SpatialLayerStyle(layer=laag, style=maak_stijl("y"), name="y", order=3, vervangt=standaardrij)
    with pytest.raises(IntegrityError), transaction.atomic():
        SpatialLayerStyle.objects.bulk_create([rij])


def test_vervangt_alleen_een_applicatiebrede_rij_van_dezelfde_laag(maak_laag):
    laag = maak_laag("algemeen")
    andere_laag = maak_laag("ander")
    elders = koppel(andere_laag, maak_stijl("elders"))
    with pytest.raises(ValidationError):
        koppel(laag, maak_stijl("a", **org(1)), vervangt=elders, **org(1))

    eigen = koppel(laag, maak_stijl("eigen", **org(1)), **org(1))
    with pytest.raises(ValidationError):
        koppel(laag, maak_stijl("b", **org(1)), vervangt=eigen, **org(1))


def test_standaardrij_weg_dan_variant_weg_en_variant_weg_dan_standaard_blijft(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    variant = koppel(laag, maak_stijl("eigen", **org(1)), vervangt=standaardrij, **org(1))
    variant.delete()
    assert SpatialLayerStyle.objects.filter(pk=standaardrij.pk).exists()

    variant = koppel(laag, maak_stijl("eigen2", **org(1)), vervangt=standaardrij, **org(1))
    standaardrij.delete()
    assert not SpatialLayerStyle.objects.filter(pk=variant.pk).exists()


# --- trigger: wie Django omzeilt (Hasura) ----------------------------------------------


def bulk(**velden) -> SpatialLayerStyle:
    """Schrijf een koppelrij zonder ``save()``, zoals Hasura dat doet."""
    velden.setdefault("order", 1)
    velden.setdefault("name", "rij")
    with transaction.atomic():
        return SpatialLayerStyle.objects.bulk_create([SpatialLayerStyle(**velden)])[0]


def test_trigger_laat_een_koppelrij_de_organisatielaag_volgen(maak_laag):
    """Een client die geen scope meestuurt (oude versie) krijgt de scope van de laag."""
    rij = bulk(layer=maak_laag("van-1", **org(1)), style=maak_stijl())
    assert scope(rij) == ("organisation", 1)
    # Ook een andere organisatie kan zo geen rij op die laag claimen.
    rij = bulk(layer=maak_laag("van-2", **org(2)), style=maak_stijl("x"), **org(1))
    assert scope(rij) == ("organisation", 2)


def test_trigger_weigert_wat_clean_ook_weigert(maak_laag):
    laag, andere_laag = maak_laag("algemeen"), maak_laag("ander")
    standaardrij = koppel(laag, maak_stijl("Status"))
    elders = koppel(andere_laag, maak_stijl("elders"))
    eigen = koppel(laag, maak_stijl("eigen", **org(1)), **org(1))

    gevallen = [
        {"access_through_id": "organisation"},  # organisatierij zonder id
        {"access_id": 1},  # applicatiebreed met id
        {"style": maak_stijl("van-2", **org(2)), **org(1)},  # stijl van een ander
        {"style": maak_stijl("van-2b", **org(2))},  # organisatiestijl op een algemene rij
        {"vervangt": elders, **org(1)},  # andere laag
        {"vervangt": eigen, **org(1)},  # geen applicatiebrede rij
    ]
    for geval in gevallen:
        geval.setdefault("style", maak_stijl(f"stijl {len(geval)} {id(geval)}"))
        with pytest.raises(IntegrityError):
            bulk(layer=laag, **geval)
    # De toegestane variant gaat wél door de trigger.
    assert bulk(layer=laag, style=maak_stijl("ok", **org(1)), vervangt=standaardrij, **org(1)).pk


def test_trigger_bewaakt_ook_een_update(maak_laag):
    laag = maak_laag("algemeen")
    rij = koppel(laag, maak_stijl("eigen", **org(1)), **org(1))
    with pytest.raises(IntegrityError), transaction.atomic():
        SpatialLayerStyle.objects.filter(pk=rij.pk).update(style=maak_stijl("van-2", **org(2)))


# --- standaard -----------------------------------------------------------------------


def test_een_standaard_per_laag_per_scope(maak_laag):
    laag = maak_laag("algemeen")
    stijl_a, stijl_b = maak_stijl("a"), maak_stijl("b")
    koppel(laag, stijl_a, standaard=True)
    koppel(laag, stijl_a, standaard=True, **org(1))
    koppel(laag, stijl_a, standaard=True, **org(2))
    with pytest.raises(ValidationError) as fout:
        koppel(laag, stijl_b, standaard=True, **org(1))
    assert "standaard" in fout.value.message_dict
    with pytest.raises(ValidationError):
        koppel(laag, stijl_b, standaard=True)
    koppel(laag, stijl_b, standaard=False, **org(1))


def test_standaard_is_standaard_uit():
    veld = SpatialLayerStyle._meta.get_field("standaard")
    assert veld.default is False and veld.db_default is False


# --- migratie 0011 -------------------------------------------------------------------


def test_kleurenset_ids_zoekt_genest():
    config = {"assen": [{"modus": "kleurenset", "kleurensetId": "a"}, {"x": [{"kleurensetId": "b"}]}], "k": None}
    assert kleurenset_ids(config) == {"a", "b"}
    assert migratie.kleurenset_ids(config) == {"a", "b"}
    assert kleurenset_ids({"kleurensetId": None}) == set()


@pytest.mark.parametrize(
    ("scopes", "verwacht"),
    [
        ([], None),
        ([("organisation", 1)], 1),
        ([("organisation", 1), ("organisation", 1)], 1),
        ([("organisation", 1), ("organisation", 2)], None),
        ([("organisation", 1), ("authenticated", None)], None),
        ([("authenticated", None)], None),
    ],
)
def test_enige_organisatie(scopes, verwacht):
    assert migratie.enige_organisatie(scopes) == verwacht


def test_migratie_wijst_scope_toe(maak_laag):
    """Koppelrij volgt de laag; stijl en kleurenset gaan alleen naar een organisatie
    als uitsluitend lagen van die ene organisatie ze gebruiken.
    """
    algemeen, van_1, ook_van_1, van_2 = (
        maak_laag("algemeen"),
        maak_laag("van-1", **org(1)),
        maak_laag("ook-van-1", **org(1)),
        maak_laag("van-2", **org(2)),
    )
    set_1 = SpatialKleurenset.objects.create(name="alleen org 1")
    set_gedeeld = SpatialKleurenset.objects.create(name="gedeeld")
    set_los = SpatialKleurenset.objects.create(name="ongebruikt")

    alleen_1 = maak_stijl("alleen 1", {"assen": [{"kleurensetId": str(set_1.pk)}]})
    gedeeld = maak_stijl("org 1 en 2", {"assen": [{"kleurensetId": str(set_gedeeld.pk)}]})
    met_algemeen = maak_stijl("org 1 en algemeen")
    los = maak_stijl("zonder laag", {"assen": [{"kleurensetId": str(set_1.pk)}]})

    # Zet de uitgangssituatie van vóór de migratie neer: alles applicatiebreed.
    rijen = [
        SpatialLayerStyle(layer=van_1, style=alleen_1, name="a", order=1),
        SpatialLayerStyle(layer=ook_van_1, style=alleen_1, name="b", order=1),
        SpatialLayerStyle(layer=van_1, style=gedeeld, name="c", order=2),
        SpatialLayerStyle(layer=van_2, style=gedeeld, name="d", order=1),
        SpatialLayerStyle(layer=van_1, style=met_algemeen, name="e", order=3),
        SpatialLayerStyle(layer=algemeen, style=met_algemeen, name="f", order=1),
    ]
    SpatialLayerStyle.objects.bulk_create(rijen)

    migratie.wijs_scope_toe(apps, None)

    assert [scope(r) for r in rijen] == [
        ("organisation", 1),
        ("organisation", 1),
        ("organisation", 1),
        ("organisation", 2),
        ("organisation", 1),
        ("authenticated", None),
    ]
    assert scope(alleen_1) == ("organisation", 1)
    assert scope(gedeeld) == ("authenticated", None)
    assert scope(met_algemeen) == ("authenticated", None)
    assert scope(los) == ("authenticated", None)
    assert scope(set_1) == ("organisation", 1)
    assert scope(set_gedeeld) == ("authenticated", None)
    assert scope(set_los) == ("authenticated", None)
    assert SpatialLayerStyle.objects.count() == 6 and SpatialStyle.objects.count() == 4


# --- upgrade naar applicatiebreed ----------------------------------------------------


def test_upgrade_neemt_stijlkoppelingen_stijlen_en_kleurensets_mee(maak_laag):
    laag = maak_laag("van-1", **org(1))
    andere = maak_laag("blijft-van-1", **org(1))
    kleurenset = SpatialKleurenset.objects.create(name="set", **org(1))
    stijl = maak_stijl("eigen", {"assen": [{"kleurensetId": str(kleurenset.pk)}]}, **org(1))
    rij = koppel(laag, stijl)
    andere_rij = koppel(andere, stijl)
    ongemoeid = maak_stijl("niet gebruikt", **org(1))

    resultaat = upgrade_laag_naar_applicatiebreed(laag.pk)

    assert resultaat["laag_omgezet"] and resultaat["stijlen_omgezet"] == 1
    assert scope(rij) == ("authenticated", None)
    assert scope(stijl) == ("authenticated", None)
    assert scope(kleurenset) == ("authenticated", None)
    # De andere laag blijft van de organisatie en verwijst nu naar een applicatiebrede stijl.
    assert scope(andere_rij) == ("organisation", 1)
    assert scope(ongemoeid) == ("organisation", 1)
