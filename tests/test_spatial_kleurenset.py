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
def test_kleurenset_zonder_categorieen_krijgt_lege_lijst_via_db_default():
    """db_default=[] i.p.v. default=list (zie modelcommentaar): een insert zonder
    categorieen — zoals Hasura die zou doen — moet toch een lege lijst opleveren.
    """
    ks = SpatialKleurenset.objects.create(name="Leeg")
    ks.refresh_from_db()
    assert ks.categorieen == []


def test_kleurenset_onopgeslagen_instantie_heeft_lege_lijst():
    """Django-default (`_lege_lijst`) is nodig náást db_default: zonder ORM-default
    is `categorieen` op een onopgeslagen instantie een `DatabaseDefault`-sentinel
    i.p.v. een bruikbare lege lijst — een footgun voor code die de instantie
    inspecteert vóór een `save()`.
    """
    ks = SpatialKleurenset(name="x")
    assert ks.categorieen == []


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


def test_categorieen_default_is_geen_kale_list():
    """Guard tegen de rgs_django_utils-interaction (zie modelcommentaar):
    `install_db_defaults_and_relation_cascading()` herkent `default is list` als
    een integer-ArrayField-signaal en zet dan een `array[]::integer[]`-default,
    wat op deze jsonb-kolom faalt. Zowel het model als migratie 0007 moeten dus
    een eigen functie gebruiken, geen kale `list`.
    """
    from importlib import import_module

    from rgs_django_spatial.models import SpatialKleurenset

    model_field = SpatialKleurenset._meta.get_field("categorieen")
    assert model_field.default is not list

    mig = import_module("rgs_django_spatial.migrations.0007_spatialkleurenset_uuid_ids")
    fields = next(
        dict(op.fields)
        for op in mig.Migration.operations
        if op.__class__.__name__ == "CreateModel" and op.name == "SpatialKleurenset"
    )
    assert fields["categorieen"].default is not list
    # Model en migratie moeten hetzelfde functie-object gebruiken (identity),
    # anders ziet makemigrations --check dit als een wijziging.
    assert fields["categorieen"].default is model_field.default
