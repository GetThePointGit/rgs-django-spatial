"""Projectniveau in de scope en ``zichtbaarheid`` (waterworks#548).

- het inplugpunt voor rollen van de consumer (``SPATIAL_PERMISSIONS_HOOK``,
  ``SPATIAL_EXTRA_SCHRIJFROLLEN``);
- ``SpatialAccess`` met projecten en ``organisatie_projecten``;
- de regels van ``SpatialLayerStyle`` op projectniveau, in ``save()`` en in de
  trigger ``spatial_layer_style_scope``.

De tests met een laag hebben PostgreSQL nodig; op de SQLite-settings worden ze
overgeslagen. Draaien::

    pytest --ds=testapp.settings_postgres tests/test_project_scope.py
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, override_settings
from rgs_django_utils.database.permission_helper import PermissionHelper

from rgs_django_spatial.access import SpatialAccess
from rgs_django_spatial.app_lagen import geen_app_rij
from rgs_django_spatial.models import (
    EnumMapZichtbaarheid,
    SpatialKleurenset,
    SpatialLayer,
    SpatialLayerStyle,
    SpatialMapLayer,
    SpatialSource,
    SpatialStyle,
    SpatialTheme,
)
from rgs_django_spatial.models._scope import ORG_SCOPE_FILTER, scope_fperm
from rgs_django_spatial.models.enums import EnumMapSourceType

TEST_TREE = {
    "public": [],
    "auth": ["public"],
    "project_read": ["auth"],
    "proj_man": ["project_read"],
    "org_mem": ["auth"],
    "org_adm": ["org_mem"],
    "sys_adm": ["proj_man", "org_adm"],
}

PROJECT_LEZEN = {"access_through_id": {"_eq": "project"}, "access_id": {"_eq": "x-hasura-test-lezen"}}
PROJECT_BEHEER = {"access_through_id": {"_eq": "project"}, "access_id": {"_eq": "x-hasura-test-beheer"}}

SCOPE_MODELLEN = [
    SpatialSource,
    SpatialLayer,
    SpatialTheme,
    SpatialStyle,
    SpatialKleurenset,
    SpatialLayerStyle,
    SpatialMapLayer,
]


def rechten_van_de_consumer(tabel: str) -> dict:
    """Voorbeeld van een hook: projectrollen op elke tabel behalve het thema."""
    if tabel == "spatial_theme":
        return {}
    return {
        "project_read": {"select": PROJECT_LEZEN},
        "proj_man": {"insert": PROJECT_BEHEER, "update": PROJECT_BEHEER, "delete": PROJECT_BEHEER},
    }


# --- inplugpunt voor rollen van de consumer ----------------------------------------------


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestZonderHook(SimpleTestCase):
    """Zonder settings krijgen projectrollen niets extra's (urbanworks blijft gelijk)."""

    def test_projectrollen_erven_alleen_de_select_van_auth(self):
        helper = PermissionHelper()
        for model in SCOPE_MODELLEN:
            with self.subTest(model=model.__name__):
                rechten = helper.get_rol_table_permissions(model)
                self.assertEqual(rechten["project_read"]["select"], {})
                for actie in ("insert", "update", "delete"):
                    self.assertIsNone(rechten["proj_man"][actie])

    def test_scope_fperm_zonder_extra_rollen_is_een_gewone_fperm(self):
        rechten = scope_fperm("---", auth="-s-", org_adm="is-", sys_adm="isu")
        self.assertEqual(rechten.config, {"auth": "-s-", "org_adm": "is-", "sys_adm": "isu", "public": "---"})


@override_settings(
    PERMISSION_TREE=TEST_TREE,
    SPATIAL_PERMISSIONS_HOOK="test_project_scope.rechten_van_de_consumer",
)
class TestMetHook(SimpleTestCase):
    def setUp(self):
        self.helper = PermissionHelper()

    def test_hook_voegt_rollen_toe_per_tabel(self):
        for model in (SpatialStyle, SpatialKleurenset, SpatialLayerStyle, SpatialMapLayer):
            with self.subTest(model=model.__name__):
                rechten = self.helper.get_rol_table_permissions(model)
                self.assertEqual(rechten["project_read"]["select"], PROJECT_LEZEN)
                self.assertEqual(rechten["proj_man"]["insert"], PROJECT_BEHEER)
                self.assertEqual(rechten["proj_man"]["update"], PROJECT_BEHEER)
                self.assertEqual(rechten["proj_man"]["delete"], PROJECT_BEHEER)

    def test_tabel_zonder_regel_in_de_hook_blijft_ongewijzigd(self):
        rechten = self.helper.get_rol_table_permissions(SpatialTheme)
        self.assertEqual(rechten["project_read"]["select"], {})
        self.assertIsNone(rechten["proj_man"]["insert"])

    def test_app_rijen_blijven_ook_voor_de_extra_rollen_dicht(self):
        """Update en delete van bron en laag sluiten app-rijen uit (urbanworks#252)."""
        for model, kolom in ((SpatialSource, "source_config"), (SpatialLayer, "params")):
            with self.subTest(model=model.__name__):
                rechten = self.helper.get_rol_table_permissions(model)["proj_man"]
                verwacht = {"_and": [PROJECT_BEHEER, geen_app_rij(kolom)]}
                self.assertEqual(rechten["update"], verwacht)
                self.assertEqual(rechten["delete"], verwacht)
                self.assertEqual(rechten["insert"], PROJECT_BEHEER)

    def test_bestaande_rollen_houden_hun_regel(self):
        for model in (SpatialStyle, SpatialKleurenset):
            with self.subTest(model=model.__name__):
                rechten = self.helper.get_rol_table_permissions(model)
                self.assertEqual(rechten["auth"]["select"], {})
                self.assertEqual(rechten["org_adm"]["update"], ORG_SCOPE_FILTER)
                self.assertEqual(rechten["sys_adm"]["update"], {})


@override_settings(PERMISSION_TREE=TEST_TREE, SPATIAL_EXTRA_SCHRIJFROLLEN=["proj_man"])
class TestExtraSchrijfrollen(SimpleTestCase):
    def test_extra_rol_volgt_het_masker_van_org_adm(self):
        rechten = scope_fperm("---", auth="-s-", org_adm="is-", sys_adm="isu")
        self.assertEqual(rechten.config["proj_man"], "is-")

    def test_eigen_masker_van_de_extra_rol_wint(self):
        rechten = scope_fperm("---", org_adm="isu", proj_man="i--")
        self.assertEqual(rechten.config["proj_man"], "i--")

    def test_zonder_org_adm_komt_er_niets_bij(self):
        self.assertNotIn("proj_man", scope_fperm("---", auth="isu").config)


@override_settings(PERMISSION_TREE=TEST_TREE, SPATIAL_PERMISSIONS_HOOK="bestaat.niet")
class TestKapotteHook(SimpleTestCase):
    def test_een_onvindbare_hook_valt_niet_stil_terug(self):
        with self.assertRaises(ImportError):
            SpatialStyle.get_permissions()


# --- SpatialAccess ----------------------------------------------------------------------


class Rij:
    """Stub met de scopekolommen en eventueel ``zichtbaarheid``."""

    def __init__(self, through, access_id=None, zichtbaarheid=None):
        self.access_through_id = through
        self.access_id = access_id
        if zichtbaarheid is not None:
            self.zichtbaarheid_id = zichtbaarheid


PROJECT_7 = Rij("project", 7)
PROJECT_8 = Rij("project", 8)
ORG_1_LEDEN = Rij("organisation", 1, "organisatie_leden")
ORG_1_PROJECTEN = Rij("organisation", 1, "organisatie_projecten")
ORG_1_STIJL = Rij("organisation", 1)


def test_projectrij_alleen_leesbaar_voor_wie_het_project_leest():
    toegang = SpatialAccess(lees_project_ids=frozenset({7}))
    assert toegang.mag_lezen(PROJECT_7)
    assert not toegang.mag_lezen(PROJECT_8)
    # Lid zijn van een organisatie met hetzelfde id geeft geen toegang tot het project.
    assert not SpatialAccess(lees_org_ids=frozenset({7})).mag_lezen(PROJECT_7)


def test_projectrij_schrijven_vraagt_schrijfrecht_op_dat_project():
    lezer = SpatialAccess(lees_project_ids=frozenset({7, 8}), schrijf_project_ids=frozenset({7}))
    assert lezer.mag_schrijven(PROJECT_7)
    assert not lezer.mag_schrijven(PROJECT_8)
    assert lezer.kan_schrijven()
    # Schrijfrecht op een organisatie met hetzelfde id telt niet voor het project.
    org_beheerder = SpatialAccess(lees_project_ids=frozenset({7}), schrijf_org_ids=frozenset({7}))
    assert not org_beheerder.mag_schrijven(PROJECT_7)


def test_projectdeelnemer_leest_alleen_organisatierijen_voor_projecten():
    deelnemer = SpatialAccess(lees_org_ids_via_project=frozenset({1}))
    assert deelnemer.mag_lezen(ORG_1_PROJECTEN)
    assert not deelnemer.mag_lezen(ORG_1_LEDEN)
    # Een rij zonder het veld (stijl, kleurenset) telt als organisatie_projecten.
    assert deelnemer.mag_lezen(ORG_1_STIJL)
    assert not deelnemer.mag_lezen(Rij("organisation", 2, "organisatie_projecten"))
    # Lezen via een project geeft nooit schrijfrecht.
    assert not deelnemer.mag_schrijven(ORG_1_PROJECTEN)


def test_lid_leest_ook_de_rijen_alleen_voor_leden():
    assert SpatialAccess(lees_org_ids=frozenset({1})).mag_lezen(ORG_1_LEDEN)


def test_lees_filter_zonder_projecten_is_ongewijzigd():
    from django.db.models import Q

    verwacht = Q(access_through_id="authenticated") | Q(access_through_id="organisation", access_id__in=frozenset({1}))
    assert SpatialAccess(lees_org_ids=frozenset({1})).lees_filter() == verwacht


# --- database: bronnen, lagen en koppelrijen -----------------------------------------------

pg = pytest.mark.django_db

ALGEMEEN = {"access_through_id": "authenticated", "access_id": None}


def org(org_id: int) -> dict:
    return {"access_through_id": "organisation", "access_id": org_id}


def project(project_id: int) -> dict:
    return {"access_through_id": "project", "access_id": project_id}


def scope(rij) -> tuple:
    rij.refresh_from_db()
    return (rij.access_through_id, rij.access_id)


@pytest.fixture
def maak_laag(db):
    if connection.vendor != "postgresql":
        pytest.skip("heeft PostgreSQL nodig (--ds=testapp.settings_postgres)")
    EnumMapSourceType.objects.get_or_create(id="wms", defaults={"name": "wms"})

    def maak(naam, zichtbaarheid=None, **scope_velden):
        extra = {} if zichtbaarheid is None else {"zichtbaarheid_id": zichtbaarheid}
        bron = SpatialSource.objects.create(
            name=f"bron {naam}", source_type_id="wms", source_config={}, tile_status="klaar", **extra, **scope_velden
        )
        return SpatialLayer.objects.create(name=naam, source=bron, **extra, **scope_velden)

    return maak


def maak_stijl(naam="stijl", **scope_velden):
    return SpatialStyle.objects.create(name=naam, style_config={"versie": 3}, **scope_velden)


def koppel(laag, stijl, **velden):
    velden.setdefault("name", stijl.name)
    velden.setdefault("order", 1)
    return SpatialLayerStyle.objects.create(layer=laag, style=stijl, **velden)


def bulk(**velden) -> SpatialLayerStyle:
    """Schrijf een koppelrij zonder ``save()``, zoals Hasura dat doet."""
    velden.setdefault("order", 1)
    velden.setdefault("name", "rij")
    with transaction.atomic():
        return SpatialLayerStyle.objects.bulk_create([SpatialLayerStyle(**velden)])[0]


@pg
def test_migratie_zet_de_enum_rijen_neer():
    if connection.vendor != "postgresql":
        pytest.skip("heeft PostgreSQL nodig (--ds=testapp.settings_postgres)")
    assert set(EnumMapZichtbaarheid.objects.values_list("id", flat=True)) == {
        "organisatie_leden",
        "organisatie_projecten",
    }


@pg
def test_zichtbaarheid_is_standaard_organisatie_projecten(maak_laag):
    laag = maak_laag("van-1", **org(1))
    laag.refresh_from_db()
    assert laag.zichtbaarheid_id == "organisatie_projecten"
    assert laag.source.zichtbaarheid_id == "organisatie_projecten"


@pg
def test_lees_filter_volgt_dezelfde_regel_als_mag_lezen(maak_laag):
    rijen = {
        "algemeen": maak_laag("algemeen").source,
        "leden": maak_laag("leden", zichtbaarheid="organisatie_leden", **org(1)).source,
        "projecten": maak_laag("projecten", **org(1)).source,
        "andere org": maak_laag("andere org", **org(2)).source,
        "project 7": maak_laag("project 7", **project(7)).source,
        "project 8": maak_laag("project 8", **project(8)).source,
    }
    gevallen = {
        "lid van 1": SpatialAccess(lees_org_ids=frozenset({1})),
        "deelnemer project 7 van org 1": SpatialAccess(
            lees_project_ids=frozenset({7}), lees_org_ids_via_project=frozenset({1})
        ),
        "niemand": SpatialAccess(),
        "staf": SpatialAccess(lees_alles=True),
    }
    verwacht = {
        "lid van 1": {"algemeen", "leden", "projecten"},
        "deelnemer project 7 van org 1": {"algemeen", "projecten", "project 7"},
        "niemand": {"algemeen"},
        "staf": set(rijen),
    }
    for naam, toegang in gevallen.items():
        via_filter = set(SpatialSource.objects.filter(toegang.lees_filter()).values_list("pk", flat=True))
        via_rij = {rij.pk for rij in rijen.values() if toegang.mag_lezen(rij)}
        assert via_filter == via_rij == {rijen[sleutel].pk for sleutel in verwacht[naam]}, naam


@pg
def test_naam_is_uniek_per_project(maak_laag):
    maak_laag("peilbuizen", **project(7))
    maak_laag("peilbuizen", **project(8))
    maak_laag("peilbuizen", **org(7))
    with pytest.raises(IntegrityError), transaction.atomic():
        maak_laag("peilbuizen", **project(7))


@pg
def test_koppelrij_op_een_projectlaag_volgt_de_laag(maak_laag):
    laag = maak_laag("van-project", **project(7))
    assert scope(koppel(laag, maak_stijl())) == ("project", 7)
    # Ook een organisatie of een ander project kan zo geen rij op die laag claimen.
    assert scope(koppel(laag, maak_stijl("b"), **org(1))) == ("project", 7)
    assert scope(bulk(layer=laag, style=maak_stijl("c"), **project(8))) == ("project", 7)


@pg
def test_project_mag_een_eigen_rij_op_een_organisatielaag_hangen(maak_laag):
    laag = maak_laag("van-1", **org(1))
    assert scope(koppel(laag, maak_stijl("p", **project(7)), **project(7))) == ("project", 7)
    assert scope(bulk(layer=laag, style=maak_stijl("q", **project(8)), **project(8))) == ("project", 8)
    # Zonder projectscope blijft de regel van urbanworks#433 gelden.
    assert scope(koppel(laag, maak_stijl("o"))) == ("organisation", 1)


@pg
def test_projectrij_zonder_project_id_wordt_geweigerd(maak_laag):
    laag = maak_laag("algemeen")
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl(), access_through_id="project")
    assert "access_id" in fout.value.message_dict
    with pytest.raises(IntegrityError):
        bulk(layer=laag, style=maak_stijl("x"), access_through_id="project")


@pg
def test_projectstijl_hoort_alleen_bij_een_rij_van_dat_project(maak_laag):
    laag = maak_laag("algemeen")
    koppel(laag, maak_stijl("eigen", **project(7)), **project(7))
    for scope_velden in (project(8), org(7), ALGEMEEN):
        with pytest.raises(ValidationError) as fout:
            koppel(laag, maak_stijl(f"p {scope_velden}", **project(7)), **scope_velden)
        assert "style" in fout.value.message_dict
        with pytest.raises(IntegrityError):
            bulk(layer=laag, style=maak_stijl(f"q {scope_velden}", **project(7)), **scope_velden)


@pg
def test_projectrij_mag_een_organisatiestijl_dragen(maak_laag):
    """Welke organisatie bij een project hoort weet het pakket niet; lezen regelt de stijl zelf."""
    laag = maak_laag("algemeen")
    koppel(laag, maak_stijl("van-1", **org(1)), **project(7))
    bulk(layer=laag, style=maak_stijl("van-2", **org(2)), **project(7))


@pg
def test_project_vervangt_een_standaardrij_en_een_organisatierij(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    van_org = koppel(laag, maak_stijl("Eigen", **org(1)), **org(1))
    a = koppel(laag, maak_stijl("a", **project(7)), vervangt=standaardrij, **project(7))
    b = koppel(laag, maak_stijl("b", **project(7)), vervangt=van_org, **project(7))
    assert list(standaardrij.vervangers.all()) == [a]
    assert list(van_org.vervangers.all()) == [b]
    # Dezelfde regels voor wie save() omzeilt.
    bulk(layer=laag, style=maak_stijl("c", **project(8)), vervangt=standaardrij, **project(8))
    bulk(layer=laag, style=maak_stijl("d", **project(8)), vervangt=van_org, **project(8))


@pg
def test_organisatie_en_project_met_hetzelfde_id_hebben_elk_een_variant(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    koppel(laag, maak_stijl("org", **org(7)), vervangt=standaardrij, **org(7))
    koppel(laag, maak_stijl("project", **project(7)), vervangt=standaardrij, **project(7))
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl("project 2", **project(7)), vervangt=standaardrij, **project(7))
    assert "vervangt" in fout.value.message_dict
    with pytest.raises(IntegrityError):
        bulk(layer=laag, style=maak_stijl("project 3", **project(7)), vervangt=standaardrij, **project(7))


@pg
def test_geen_ketens_en_geen_vervanging_omhoog(maak_laag):
    laag = maak_laag("algemeen")
    standaardrij = koppel(laag, maak_stijl("Status"))
    variant_org = koppel(laag, maak_stijl("variant", **org(1)), vervangt=standaardrij, **org(1))
    van_project = koppel(laag, maak_stijl("project", **project(7)), **project(7))

    gevallen = [
        # een variant vervangen (keten)
        {"vervangt": variant_org, "style": lambda: maak_stijl(**project(7)), **project(7)},
        # een projectrij vervangen, door een ander project of een organisatie
        {"vervangt": van_project, "style": lambda: maak_stijl(**project(8)), **project(8)},
        {"vervangt": van_project, "style": lambda: maak_stijl(**org(1)), **org(1)},
    ]
    for nummer, geval in enumerate(gevallen):
        maak = geval.pop("style")
        with pytest.raises(ValidationError) as fout:
            koppel(laag, maak(), name=f"clean {nummer}", **geval)
        assert "vervangt" in fout.value.message_dict, nummer
        with pytest.raises(IntegrityError):
            bulk(layer=laag, style=maak(), name=f"trigger {nummer}", **geval)


@pg
def test_een_standaard_per_laag_per_scope(maak_laag):
    laag = maak_laag("algemeen")
    koppel(laag, maak_stijl("a"), standaard=True)
    koppel(laag, maak_stijl("b", **org(7)), standaard=True, **org(7))
    koppel(laag, maak_stijl("c", **project(7)), standaard=True, **project(7))
    with pytest.raises(ValidationError) as fout:
        koppel(laag, maak_stijl("d", **project(7)), standaard=True, **project(7))
    assert "standaard" in fout.value.message_dict
