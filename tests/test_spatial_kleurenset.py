"""Pure model-tests voor SpatialKleurenset en de uuid-ids (sqlite in-memory, geen Postgres)."""

import uuid

import pytest

from rgs_django_spatial.models import SpatialKleurenset, SpatialLayerStyle, SpatialStyle


@pytest.mark.django_db
def test_kleurenset_krijgt_uuid_en_bewaart_categorieen():
    ks = SpatialKleurenset.objects.create(
        name="Baggerklasse",
        categorieen=[{"waarde": "A", "label": "Klasse A", "kleur": "#ff0000"}],
    )
    assert isinstance(ks.id, uuid.UUID)
    ks.refresh_from_db()
    assert ks.categorieen[0]["kleur"] == "#ff0000"
    assert str(ks) == "Baggerklasse"


@pytest.mark.django_db
def test_style_id_is_uuid_en_layer_style_fk_volgt():
    st = SpatialStyle.objects.create(name="s", style_config={"versie": 3, "lagen": []})
    assert isinstance(st.id, uuid.UUID)
    fk = SpatialLayerStyle._meta.get_field("style")
    assert fk.target_field.get_internal_type() == "UUIDField"


def test_kleurenset_permissies_gelijk_aan_style():
    assert SpatialKleurenset.get_permissions()["auth"] == SpatialStyle.get_permissions()["auth"]


def test_migratie_0007_zet_db_default_gen_random_uuid():
    """De DB-default is nodig omdat Hasura zonder id insert (spec §4)."""
    from importlib import import_module

    mig = import_module("rgs_django_spatial.migrations.0007_spatialkleurenset_uuid_ids")
    velden = [
        op.fields
        for op in mig.Migration.operations
        if op.__class__.__name__ == "CreateModel" and op.name in ("SpatialKleurenset", "SpatialStyle")
    ]
    assert len(velden) == 2
    for fields in velden:
        id_field = dict(fields)["id"]
        assert id_field.db_default.function == "gen_random_uuid"
