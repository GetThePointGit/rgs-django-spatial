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
def test_kleurenset_zonder_categorieen_krijgt_lege_lijst_via_orm_default():
    """Let op: dit oefent het Django-default (`_lege_lijst`) uit, niet de DB-default.

    De Django-ORM stuurt bij een ``.objects.create()`` altijd de Python-default
    (`_lege_lijst`) mee in de insert, ook als de kolom een `db_default` heeft —
    de DB-default wordt dus door deze test nooit geraakt (die is alleen voor een
    insert die de kolom overslaat, zoals Hasura zonder `categorieen` in de
    payload doet). Zie ``test_categorieen_db_default_declaratie`` hieronder voor
    de check op de `db_default`-declaratie zelf.
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
    """Kleurenset volgt hetzelfde org_adm-mutatiepatroon als SpatialStyle (d67c8b6):
    `auth` mag alleen selecteren, insert/update/delete staan alleen op `org_adm`.
    """
    kleurenset_perms = SpatialKleurenset.get_permissions()
    style_perms = SpatialStyle.get_permissions()
    assert kleurenset_perms["auth"] == style_perms["auth"]
    assert kleurenset_perms["org_adm"] == style_perms["org_adm"]

    # Pin de concrete contract, niet alleen de gelijkheid met SpatialStyle.
    assert kleurenset_perms["auth"] == {"select": {}}
    assert kleurenset_perms["org_adm"] == {"insert": {}, "update": {}, "delete": {}}


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


def test_model_id_velden_hebben_db_default_gen_random_uuid():
    """Zelfde check als hierboven, maar dan op het MODEL i.p.v. alleen de migratie."""
    for model in (SpatialKleurenset, SpatialStyle):
        id_field = model._meta.get_field("id")
        assert id_field.db_default.function == "gen_random_uuid"


def test_categorieen_db_default_declaratie():
    """`db_default` van `categorieen` is een kale lege lijst (`[]`), zowel op het
    model als op de `CreateModel`-operatie in migratie 0007 — geen `Value`-wrapper
    (in tegenstelling tot bv. `gen_random_uuid()`, dat wél in een `Func` zit).
    """
    from importlib import import_module

    model_field = SpatialKleurenset._meta.get_field("categorieen")
    assert model_field.db_default == []

    mig = import_module("rgs_django_spatial.migrations.0007_spatialkleurenset_uuid_ids")
    fields = next(
        dict(op.fields)
        for op in mig.Migration.operations
        if op.__class__.__name__ == "CreateModel" and op.name == "SpatialKleurenset"
    )
    assert fields["categorieen"].db_default == []


def test_categorieen_default_is_geen_kale_list():
    """Guard tegen de rgs_django_utils-interaction (zie modelcommentaar):
    `install_db_defaults_and_relation_cascading()` herkent `default is list` als
    een integer-ArrayField-signaal en zet dan een `array[]::integer[]`-default,
    wat op deze jsonb-kolom faalt. Zowel het model als migratie 0007 moeten dus
    een eigen functie gebruiken, geen kale `list`.
    """
    from importlib import import_module

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
