from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps


class SpatialSource(models.Model):
    """Kaartbron voor gebruik in lagen."""

    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_source_pkey en
    # stuurt 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    name = models.TextStringField(
        verbose_name="naam",
        unique=True,
        config=models.Config(
            doc_short="Naam van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    description = models.TextStringField(
        verbose_name="omschrijving",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    source_type = models.ForeignKey(
        "EnumMapSourceType",
        on_delete=models.PROTECT,
        verbose_name="source type",
        config=models.Config(
            doc_short="Type van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    source_config = models.JSONField(
        verbose_name="source configuratie",
        config=models.Config(
            doc_short="Configuratie van de kaartbron, afhankelijk van het type",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    geojson_file = models.FileField(
        upload_to="spatial_sources/geojson/",
        verbose_name="geojson bestand",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="GeoJSON bestand voor GeoJSON kaartbronnen. bestand in wgs84 coördinatenstelsel",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    file = models.FileField(
        upload_to="spatial_sources/files/",
        verbose_name="bestand",
        null=True,
        blank=True,
        help_text="GeoPackage (.gpkg) of GeoJSON (.geojson) voor bestand-bronnen (tiling in fase 2).",
        config=models.Config(
            doc_short="Bronbestand voor bestand-bronnen; wordt in fase 2 naar PMTiles omgezet",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    tile_status = models.TextStringField(
        "tile status",
        default="geen",
        config=models.Config(
            doc_short="Status van tile-generatie: geen|bezig|klaar|fout (fase 2)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    tile_fout = models.TextField(
        "tile foutmelding",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Foutmelding van de laatste tile-generatie (fase 2)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    reproject = models.BooleanField(
        "herprojecteren via MapProxy",
        default=False,
        config=models.Config(
            doc_short="Of deze WMS-bron via MapProxy naar EPSG:3857 geherprojecteerd moet worden (fase 2)",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    tiles_updated_at = models.DateTimeField(
        "tiles bijgewerkt op",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Moment van de laatste geslaagde tile-generatie (voor WFS-verversing)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )

    authentication_type = models.ForeignKey(
        "EnumMapAuthType",
        on_delete=models.PROTECT,
        verbose_name="authenticatie type",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Type van authenticatie voor de kaartbron, indien nodig",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    authentication_config = models.JSONField(
        verbose_name="authenticatie configuratie",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Configuratie van de authenticatie voor de kaartbron, indien nodig",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_source"
        verbose_name = "kaartbron"
        verbose_name_plural = "kaartbronnen"

    class TableDescription:
        section = section_maps
        order = 5
        modules = "*"

    def __str__(self):
        return self.name

    @classmethod
    def get_permissions(cls):
        no_filt = {}

        return models.TPerm(
            public=None,
            auth={
                "select": no_filt,
                "insert": no_filt,
                "update": no_filt,
                "delete": no_filt,
            },
        )
