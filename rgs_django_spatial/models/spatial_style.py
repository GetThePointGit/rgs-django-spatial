from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps


class SpatialStyle(models.Model):
    """Mapbox stijl voor gebruik in lagen."""

    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_style_pkey en stuurt
    # 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    name = models.TextStringField(
        verbose_name="naam",
        config=models.Config(
            doc_short="Naam van de kaartbron",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    notes = models.TextStringField(
        verbose_name="opmerkingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="opmerkingen bij stijl",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    style_config = models.JSONField(
        verbose_name="stijl configuratie",
        config=models.Config(
            doc_short="Configuratie van de stijl, afhankelijk van het type",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_style"
        verbose_name = "kaart stijl"
        verbose_name_plural = "kaart stijlen"
        ordering = ["name"]

    class TableDescription:
        section = section_maps
        order = 7
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
