from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from ._sections import section_maps


class SpatialMap(models.Model):
    """Kaart bestaande uit verschillende lagen."""

    name = models.TextStringField(
        verbose_name="naam",
        unique=True,
        config=models.Config(
            doc_short="Naam van de kaart",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    description = models.TextField(
        verbose_name="omschrijving",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Omschrijving van de kaart",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    icon = models.TextStringField(
        verbose_name="icoon",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Icoon van de kaartlaag (bijv. URL naar afbeelding)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van de kaarten in de lijst (laagste index wordt eerst getoond)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )

    access_through = models.ForeignKey(
        EnumAccessThrough,
        on_delete=models.PROTECT,
        verbose_name="toegang via",
        config=models.Config(
            doc_short="Toegang via (publiek, organisatie)",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )
    access_id = models.IntegerField(
        verbose_name="toegang id",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="ID van de organisatie of het project waartoe deze kaartlaag behoort, indien van toepassing",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )

    # todo: link for access by generic relation in view?

    warnings = models.JSONField(
        verbose_name="waarschuwingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Eventuele waarschuwingen of opmerkingen over de kaartlaag",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )

    default_extent = models.ArrayField(
        models.FloatField(),
        size=4,
        verbose_name="extent",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Extent van de kaartlaag als [minX, minY, maxX, maxY] in wgs84 bij laden van de kaart",
            permissions=models.FPerm("---", auth="-s-"),
        ),
    )

    class Meta:
        db_table = "spatial_map"
        verbose_name = "kaart"
        verbose_name_plural = "kaart"

    class TableDescription:
        section = section_maps
        order = 1
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
            },
        )
