"""Modulevelden op SpatialLayerStyle (waterworks modules-spec §5.3).

``modules`` is het masker (letters waarin de stijl kiesbaar is, ``None`` =
alle modules); ``standaard_in`` de letters waarin hij voorgeselecteerd is. Per
laag hoogstens één standaard per letter. De validatie is puur getest; de
DB-query voor de andere koppelingen wordt gemockt (sqlite kan de laag-keten
met ArrayFields niet goed opbouwen). Waterworks test het DB-pad op Postgres.
"""

import importlib
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db.migrations import AddField

from rgs_django_spatial.models import SpatialLayerStyle
from rgs_django_spatial.models.spatial_layer_style import normaliseer_masker, valideer_module_velden


def test_normaliseer_masker():
    assert normaliseer_masker(None) is None
    assert normaliseer_masker("") is None
    assert normaliseer_masker("   ") is None
    assert normaliseer_masker(" DP ") == "DP"


@pytest.mark.parametrize(
    ("modules", "standaard_in", "andere"),
    [
        (None, None, []),
        ("DP", "D", [None, "P"]),
        (None, "DP", ["O"]),
    ],
)
def test_geldige_combinaties(modules, standaard_in, andere):
    assert valideer_module_velden(modules, standaard_in, andere) == {}


@pytest.mark.parametrize("waarde", ["D P", "D1"])
def test_alleen_hoofdletters(waarde):
    assert valideer_module_velden(waarde, None, []) == {"modules": ["Alleen hoofdletters A-Z, zonder spaties."]}
    assert valideer_module_velden(None, waarde, []) == {"standaard_in": ["Alleen hoofdletters A-Z, zonder spaties."]}


def test_kleine_letters_geven_hoofdletter_hint():
    assert valideer_module_velden("dp", None, []) == {"modules": ["Gebruik hoofdletters: DP."]}
    assert valideer_module_velden(None, "dp", []) == {"standaard_in": ["Gebruik hoofdletters: DP."]}


def test_kleine_letters_gemengd_met_hoofdletters_meldt_alleen_de_kleine():
    assert valideer_module_velden("Dp", None, []) == {"modules": ["Gebruik hoofdletters: P."]}


@pytest.mark.parametrize("waarde", ["dp1", "d p"])
def test_kleine_letters_gemengd_met_onbekende_tekens_geeft_generieke_melding(waarde):
    assert valideer_module_velden(waarde, None, []) == {"modules": ["Alleen hoofdletters A-Z, zonder spaties."]}
    assert valideer_module_velden(None, waarde, []) == {"standaard_in": ["Alleen hoofdletters A-Z, zonder spaties."]}


def test_elke_letter_hoogstens_een_keer():
    assert valideer_module_velden("DD", None, []) == {"modules": ["Elke letter hoogstens één keer."]}


def test_standaard_moet_beschikbaar_zijn():
    assert valideer_module_velden("P", "D", []) == {
        "standaard_in": ["Standaard in D, maar daar niet beschikbaar (modules=P)."]
    }


def test_een_standaard_per_letter_per_laag():
    assert valideer_module_velden(None, "DP", ["P", None]) == {
        "standaard_in": ["Deze kaartlaag heeft al een standaardstijl voor P."]
    }


def test_clean_meldt_een_dubbele_standaard():
    koppeling = SpatialLayerStyle(layer_id=1, name="Meetstatus", order=1, standaard_in="D")
    with patch.object(SpatialLayerStyle, "_andere_standaard_in", return_value=["D"]):
        with pytest.raises(ValidationError) as fout:
            koppeling.clean()
    assert fout.value.message_dict == {"standaard_in": ["Deze kaartlaag heeft al een standaardstijl voor D."]}


def test_save_weigert_voordat_er_iets_naar_de_database_gaat():
    # Geen django_db-marker: een DB-aanraking zou deze test laten falen.
    koppeling = SpatialLayerStyle(layer_id=1, name="Meetstatus", order=1, standaard_in="D")
    with patch.object(SpatialLayerStyle, "_andere_standaard_in", return_value=["D"]):
        with pytest.raises(ValidationError):
            koppeling.save()


def test_lege_waarden_worden_null():
    koppeling = SpatialLayerStyle(layer_id=1, name="Standaard", order=0, modules="", standaard_in="  ")
    with patch.object(SpatialLayerStyle, "_andere_standaard_in", return_value=[]) as andere:
        koppeling._valideer_modules()
    assert koppeling.modules is None
    assert koppeling.standaard_in is None
    andere.assert_not_called()


def test_zonder_standaard_geen_query_naar_andere_koppelingen():
    koppeling = SpatialLayerStyle(layer_id=1, name="Toetsklasse", order=2, modules="P")
    with patch.object(SpatialLayerStyle, "_andere_standaard_in") as andere:
        koppeling._valideer_modules()
    andere.assert_not_called()


def test_velden_zijn_optioneel():
    for naam in ("modules", "standaard_in"):
        veld = SpatialLayerStyle._meta.get_field(naam)
        assert veld.null and veld.blank


def test_migratie_0008_voegt_beide_velden_toe():
    migratie = importlib.import_module("rgs_django_spatial.migrations.0008_spatiallayerstyle_modules")
    velden = {(op.model_name, op.name) for op in migratie.Migration.operations if isinstance(op, AddField)}
    assert velden == {("spatiallayerstyle", "modules"), ("spatiallayerstyle", "standaard_in")}
