from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps


class SpatialLayerStyle(models.Model):
    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_layer_style_pkey en
    # stuurt 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    layer = models.ForeignKey(
        "SpatialLayer",
        on_delete=models.CASCADE,
        verbose_name="kaartlaag",
        related_name="styles",
        config=models.Config(
            doc_short="Kaartlaag waartoe deze stijl behoort",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    style = models.ForeignKey(
        "SpatialStyle",
        on_delete=models.PROTECT,
        verbose_name="stijl",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Stijl van de kaartlaag",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    name = models.TextStringField(
        verbose_name="naam",
        config=models.Config(
            doc_short="Naam van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    order = models.IntegerField(
        verbose_name="volgorde",
        config=models.Config(
            doc_short="Volgorde van de stijlen binnen de kaartlaag. Lage getallen worden eerst getoond",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    active = models.BooleanField(
        verbose_name="selecteerbaar",
        default=False,
        config=models.Config(
            doc_short="Geeft aan of deze stijl selecteerbaar is",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    warnings = models.JSONField(
        verbose_name="waarschuwingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Eventuele waarschuwingen met betrekking tot deze stijl gekoppeld aan deze laag",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_layer_style"
        verbose_name = "kaartlaag stijl"
        verbose_name_plural = "kaartlaag stijlen"
        ordering = ["layer", "order"]

        constraints = [
            models.UniqueConstraint(
                fields=["layer", "style"],
                name="unique_layer_style",
            )
        ]

    class TableDescription:
        section = section_maps
        order = 6
        modules = "*"

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
