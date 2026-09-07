# Handgeschreven (spec §4): spatial_style en spatial_layer_style worden
# weggegooid en herbouwd omdat een bigint→uuid-AlterField geen bestaande rijen
# kan converteren. Er is geen productiedata (waterworks draait nog niet live).

import uuid

import django.db.models.deletion
import rgs_django_utils.database.dj_extended_models
from django.db import migrations, models

# Zelfde functie-object als het model (niet opnieuw gedefinieerd): makemigrations
# vergelijkt defaults op identiteit, dus een losse kopie zou --check laten falen.
from rgs_django_spatial.models.spatial_kleurenset import _lege_lijst


def _gen_random_uuid() -> models.Func:
    """Bouwt de db_default-expressie ``gen_random_uuid()`` (Postgres, spec §4).

    ``Func(function=...)`` legt de functienaam alleen vast in ``extra`` (gebruikt
    door ``as_sql``), niet als attribuut. We zetten ``.function`` hier expliciet
    zodat de default ook via dat attribuut inspecteerbaar is (bewaakt door
    ``tests/test_spatial_kleurenset.py::test_migratie_0007_zet_db_default_gen_random_uuid``).
    """
    func = models.Func(function="gen_random_uuid")
    func.function = "gen_random_uuid"
    return func


class Migration(migrations.Migration):
    dependencies = [
        ("rgs_django_spatial", "0006_alter_spatiallayer_name_alter_spatiallayerstyle_id_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="SpatialLayerStyle"),
        migrations.DeleteModel(name="SpatialStyle"),
        migrations.CreateModel(
            name="SpatialKleurenset",
            fields=[
                (
                    "id",
                    rgs_django_utils.database.dj_extended_models.UUIDField(
                        db_default=_gen_random_uuid(),
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", rgs_django_utils.database.dj_extended_models.CharField(max_length=200, verbose_name="naam")),
                (
                    "notes",
                    rgs_django_utils.database.dj_extended_models.TextField(
                        blank=True, null=True, verbose_name="opmerkingen"
                    ),
                ),
                (
                    "categorieen",
                    rgs_django_utils.database.dj_extended_models.JSONField(
                        db_default=[], default=_lege_lijst, verbose_name="categorieën"
                    ),
                ),
            ],
            options={
                "verbose_name": "kleurenset",
                "verbose_name_plural": "kleurensets",
                "db_table": "spatial_kleurenset",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="SpatialStyle",
            fields=[
                (
                    "id",
                    rgs_django_utils.database.dj_extended_models.UUIDField(
                        db_default=_gen_random_uuid(),
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", rgs_django_utils.database.dj_extended_models.TextStringField(verbose_name="naam")),
                (
                    "notes",
                    rgs_django_utils.database.dj_extended_models.TextStringField(
                        blank=True, null=True, verbose_name="opmerkingen"
                    ),
                ),
                (
                    "style_config",
                    rgs_django_utils.database.dj_extended_models.JSONField(verbose_name="stijl configuratie"),
                ),
            ],
            options={
                "verbose_name": "kaart stijl",
                "verbose_name_plural": "kaart stijlen",
                "db_table": "spatial_style",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="SpatialLayerStyle",
            fields=[
                (
                    "id",
                    rgs_django_utils.database.dj_extended_models.BigAutoField(primary_key=True, serialize=False),
                ),
                ("name", rgs_django_utils.database.dj_extended_models.TextStringField(verbose_name="naam")),
                ("order", rgs_django_utils.database.dj_extended_models.IntegerField(verbose_name="volgorde")),
                (
                    "active",
                    rgs_django_utils.database.dj_extended_models.BooleanField(
                        default=False, verbose_name="selecteerbaar"
                    ),
                ),
                (
                    "warnings",
                    rgs_django_utils.database.dj_extended_models.JSONField(
                        blank=True, null=True, verbose_name="waarschuwingen"
                    ),
                ),
                (
                    "layer",
                    rgs_django_utils.database.dj_extended_models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="styles",
                        to="rgs_django_spatial.spatiallayer",
                        verbose_name="kaartlaag",
                    ),
                ),
                (
                    "style",
                    rgs_django_utils.database.dj_extended_models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="rgs_django_spatial.spatialstyle",
                        verbose_name="stijl",
                    ),
                ),
            ],
            options={
                "verbose_name": "kaartlaag stijl",
                "verbose_name_plural": "kaartlaag stijlen",
                "db_table": "spatial_layer_style",
                "ordering": ["layer", "order"],
            },
        ),
        migrations.AddConstraint(
            model_name="spatiallayerstyle",
            constraint=models.UniqueConstraint(fields=("layer", "style"), name="unique_layer_style"),
        ),
    ]
