"""Bescherming van app-rijen (urbanworks#252): Hasura-filters en Django-guard."""

import pytest
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.signals import pre_delete, pre_save
from django.test import SimpleTestCase, override_settings
from rgs_django_utils.database.permission_helper import PermissionHelper
from test_permissions import TEST_TREE

from rgs_django_spatial.app_lagen import (
    AppLaagBeschermd,
    app_laag_onderhoud,
    en_geen_app_rij,
    geen_app_rij,
    is_app_bron,
    is_app_laag,
)
from rgs_django_spatial.models import EnumMapSourceType, SpatialLayer, SpatialSource, SpatialTheme
from rgs_django_spatial.models._scope import ORG_SCOPE_FILTER

ROLLEN = ("org_adm", "sys_adm", "dev", "dev_man")
KOLOMMEN = {SpatialSource: "source_config", SpatialLayer: "params"}


def test_geen_app_rij_vorm():
    assert geen_app_rij("params") == {
        "_or": [{"params": {"_is_null": True}}, {"_not": {"params": {"_has_key": "app_layer"}}}]
    }


def test_en_geen_app_rij_leeg_filter_is_exact_het_app_filter():
    assert en_geen_app_rij({}, "params") == geen_app_rij("params")
    assert en_geen_app_rij(None, "params") == geen_app_rij("params")
    assert en_geen_app_rij({"a": 1}, "params") == {"_and": [{"a": 1}, geen_app_rij("params")]}


def test_herkenning():
    assert is_app_laag(SpatialLayer(params={"app_layer": "aanvragen"}))
    assert not is_app_laag(SpatialLayer(params={"x": 1}))
    assert not is_app_laag(SpatialLayer(params=None))
    assert is_app_bron(SpatialSource(source_config={"app_layer": "aanvragen"}))
    assert not is_app_bron(SpatialSource(source_config={"url": "u"}))


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestPermissieFilters(SimpleTestCase):
    def setUp(self):
        self.helper = PermissionHelper()

    def test_update_en_delete_bevatten_het_filter_voor_alle_rollen(self):
        for model, kolom in KOLOMMEN.items():
            app = geen_app_rij(kolom)
            for rol in ROLLEN:
                perms = self.helper.get_rol_table_permissions(model)[rol]
                for actie in ("update", "delete"):
                    with self.subTest(model=model.__name__, rol=rol, actie=actie):
                        if rol == "org_adm":
                            assert perms[actie] == {"_and": [ORG_SCOPE_FILTER, app]}
                        else:
                            assert perms[actie] == app

    def test_select_en_insert_ongewijzigd(self):
        for model in KOLOMMEN:
            for rol in ROLLEN:
                perms = self.helper.get_rol_table_permissions(model)[rol]
                with self.subTest(model=model.__name__, rol=rol):
                    assert perms["insert"] == (ORG_SCOPE_FILTER if rol == "org_adm" else {})
                    assert perms["select"] == (
                        ORG_SCOPE_FILTER if (rol == "org_adm" and model is SpatialSource) else {}
                    )

    def test_andere_tabellen_ongemoeid(self):
        perms = self.helper.get_rol_table_permissions(SpatialTheme)
        assert perms["sys_adm"]["update"] == {}
        assert perms["org_adm"]["delete"] == ORG_SCOPE_FILTER


@pytest.fixture
def bron(db):
    EnumMapSourceType.objects.get_or_create(id="geojson", defaults={"name": "geojson"})

    def maak(config, naam="b"):
        with app_laag_onderhoud():
            return SpatialSource.objects.create(name=naam, source_type_id="geojson", source_config=config)

    return maak


@pytest.mark.django_db
class TestGuard:
    def test_gewone_rijen_ongewijzigd(self, bron):
        b = bron({"url": "u"})
        b.name = "nieuw"
        b.save()
        b.delete()
        assert not SpatialSource.objects.filter(pk=b.pk).exists()

    def test_verwijderen_geweigerd_en_bypass(self, bron):
        b = bron({"app_layer": "aanvragen"})
        with pytest.raises(AppLaagBeschermd), transaction.atomic():
            b.delete()
        assert SpatialSource.objects.filter(pk=b.pk).exists()
        with app_laag_onderhoud():
            b.delete()
        assert not SpatialSource.objects.filter(pk=b.pk).exists()

    def test_exception_is_permission_denied(self):
        assert issubclass(AppLaagBeschermd, PermissionDenied)

    def test_wijzigen_source_config_en_naam_geweigerd(self, bron):
        b = bron({"app_layer": "aanvragen"}, naam="oud")
        b.source_config = {"app_layer": "aanvragen", "extra": 1}
        with pytest.raises(AppLaagBeschermd):
            b.save()
        b = SpatialSource.objects.get(pk=b.pk)
        b.name = "anders"
        with pytest.raises(AppLaagBeschermd):
            b.save()
        assert SpatialSource.objects.get(pk=b.pk).name == "oud"

    def test_markering_weghalen_geweigerd(self, bron):
        b = bron({"app_layer": "aanvragen"})
        b.source_config = {"url": "u"}
        with pytest.raises(AppLaagBeschermd):
            b.save()

    def test_queryset_delete_geweigerd(self, bron):
        b = bron({"app_layer": "aanvragen"})
        with pytest.raises(AppLaagBeschermd), transaction.atomic():
            SpatialSource.objects.filter(pk=b.pk).delete()
        assert SpatialSource.objects.filter(pk=b.pk).exists()

    def test_nieuwe_app_bron_alleen_in_bypass(self, bron):
        with pytest.raises(AppLaagBeschermd):
            SpatialSource.objects.create(name="x", source_type_id="geojson", source_config={"app_layer": "a"})
        b = bron({"app_layer": "a"})
        with app_laag_onderhoud():
            b.name = "m"
            b.save()

    def test_bypass_wordt_hersteld_ook_bij_fout(self, bron):
        b = bron({"app_layer": "a"})
        with pytest.raises(RuntimeError), app_laag_onderhoud():
            raise RuntimeError
        with pytest.raises(AppLaagBeschermd):
            b.delete()


# SpatialLayer heeft een ArrayField (PostgreSQL); op SQLite kan er geen rij in. De
# receivers worden daarom via de signals zelf aangeroepen, op een instantie in het geheugen.
@pytest.mark.django_db
class TestGuardLaag:
    def test_app_laag_opslaan_en_verwijderen_geweigerd(self):
        laag = SpatialLayer(pk=5, name="l", params={"app_layer": "aanvragen"})
        with pytest.raises(AppLaagBeschermd):
            pre_save.send(SpatialLayer, instance=laag)
        with pytest.raises(AppLaagBeschermd):
            pre_delete.send(SpatialLayer, instance=laag)
        with app_laag_onderhoud():
            pre_save.send(SpatialLayer, instance=laag)
            pre_delete.send(SpatialLayer, instance=laag)

    def test_gewone_laag_ongemoeid(self):
        for params in (None, {}, {"x": 1}):
            laag = SpatialLayer(pk=5, name="l", params=params)
            pre_save.send(SpatialLayer, instance=laag)
            pre_delete.send(SpatialLayer, instance=laag)
