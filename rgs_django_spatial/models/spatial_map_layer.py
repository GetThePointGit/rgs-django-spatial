from rgs_django_utils.database import dj_extended_models as models

from ._sections import section_maps


class SpatialMapLayer(models.Model):
    """Een laag die is toegevoegd aan een kaart."""

    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_map_layer_pkey en
    # stuurt 'id' mee, dus 'id' moet in de insert_input zitten.
    id = models.BigAutoField(
        primary_key=True,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    map = models.ForeignKey(
        "SpatialMap",
        on_delete=models.CASCADE,
        verbose_name="kaart",
        config=models.Config(
            doc_short="De kaart waar deze laag deel van uitmaakt",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    layer = models.ForeignKey(
        "SpatialLayer",
        on_delete=models.CASCADE,
        verbose_name="laag",
        config=models.Config(
            doc_short="De kaartlaag die aan de kaart is toegevoegd",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    order = models.IntegerField(
        "volgorde",
        default=0,
        config=models.Config(
            doc_short="De volgorde van de laag in de kaart. laag nummer is hoger in de stapel",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    visible = models.BooleanField(
        "zichtbaar",
        default=True,
        config=models.Config(
            doc_short="Of de laag standaard zichtbaar is in de kaart",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    default_style = models.JSONField(
        "standaard stijl",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="De standaard stijl voor de laag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    default_opacity = models.FloatField(
        "standaard dekking",
        default=1.0,
        config=models.Config(
            doc_short="De standaard dekking voor de laag, tussen 0 (volledig transparant) en 1 (volledig zichtbaar)",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    theme = models.ForeignKey(
        "SpatialTheme",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="thema",
        config=models.Config(
            doc_short="Thema waaronder de laag in het lagenpaneel wordt gegroepeerd",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    default_label_field = models.TextStringField(
        "standaard labelveld",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Attribuutveld dat als tekstlabel op de kaart wordt getoond, indien ingesteld",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    default_label_visible = models.BooleanField(
        "label standaard zichtbaar",
        default=False,
        config=models.Config(
            doc_short="Of het label standaard zichtbaar is bij het aanzetten van de laag",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_map_layer"
        verbose_name = "kaart-kaartlaag"
        verbose_name_plural = "kaart-kaartlagen"

        constraints = [
            models.UniqueConstraint(fields=["map", "layer"], name="unique_map_layer"),
        ]

    class TableDescription:
        section = section_maps
        order = 2
        modules = "*"

    def __str__(self):
        return f"{self.map.name} - {self.layer.name}"

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
