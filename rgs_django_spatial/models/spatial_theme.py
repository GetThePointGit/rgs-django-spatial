from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps


class SpatialTheme(models.Model):
    """Thema waaronder kaartlagen in het lagenpaneel gegroepeerd worden."""

    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_theme_pkey en stuurt
    # 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    name = models.TextStringField(
        verbose_name="naam",
        unique=True,
        config=models.Config(
            doc_short="Naam van het thema",
            permissions=models.FPerm(auth="isu"),
        ),
    )
    order = models.IntegerField(
        verbose_name="volgorde",
        default=0,
        config=models.Config(
            doc_short="Volgorde van het thema in het lagenpaneel (laag nummer eerst)",
            permissions=models.FPerm(auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_theme"
        verbose_name = "kaartthema"
        verbose_name_plural = "kaartthema's"
        ordering = ["order", "name"]

    class TableDescription:
        section = section_maps
        order = 3
        modules = "*"

    def __str__(self):
        return self.name

    @classmethod
    def get_permissions(cls):
        no_filt = {}
        return models.TPerm(
            public=None,
            auth={"select": no_filt, "insert": no_filt, "update": no_filt, "delete": no_filt},
        )
