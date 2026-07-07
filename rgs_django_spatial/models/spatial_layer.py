from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from ._sections import section_maps

#
# - map_source
#   - internal (ww/pl/pp/bagger_cluster)
#   - internal vector tile (zelf serveren als vectortile)
#   - geojson (file/ url)
#       - style configuratie
#   - db_table/ query / geopackage (zelf serveren als Geojson/ vectortile)
#       - style configuratie
#   - external source
#     - wms/ wmts / xyz tile
#       - styles[]
#     - wfs
#       - style configuratie
#     - vector tile
#       - style configuration
#       - detail endpoint
# - external_autorisation


# layer:
#  - (source + style)[]
#  - legend?
#  - link (public/ organisation / project)


# styles:
#  - name
#  - required fields
#  - filter (where clause)


# - map:
#   - owner (public/ organisation / project)
#   - name
#   - layers []:
#       - order
#       - visible
#       - opacity
#       - min zoom
#       - max zoom
#       - active style
#   - initial extent
#   - background map (if styling - order mapping?)


# Functies:
# - get_layers (from wms/ wfs endpoint)

# map_source:
# - attributes[]


class SpatialLayer(models.Model):
    # Expliciet gedeclareerd (matcht de impliciete PK) zodat 'auth' insert mag:
    # de upsert vanuit de frontend conflicteert op spatial_layer_pkey en
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
    icon = models.TextStringField(
        verbose_name="icoon",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Icoon van de kaartlaag (bijv. URL naar afbeelding)",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    access_through = models.ForeignKey(
        EnumAccessThrough,
        on_delete=models.PROTECT,
        verbose_name="toegang via",
        config=models.Config(
            doc_short="Toegang via (publiek, organisatie, project)",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    access_id = models.IntegerField(
        verbose_name="toegang id",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="ID van de organisatie of het project waartoe deze kaartlaag behoort, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    # todo: link for access by generic relation in view?

    source = models.ForeignKey(
        "SpatialSource",
        on_delete=models.PROTECT,
        verbose_name="kaartbron",
        config=models.Config(
            doc_short="De kaartbron waar deze laag deel van uitmaakt",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    source_layer = models.TextStringField(
        verbose_name="laag in bron",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Layer binnen de kaartbron, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    params = models.JSONField(
        verbose_name="parameters",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Extra parameters voor de kaartlaag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    geometry_type = models.TextStringField(
        verbose_name="geometrie type",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Type geometrie van de kaartlaag (Point, LineString, Polygon), indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    extent = models.ArrayField(
        models.FloatField(),
        size=4,
        verbose_name="extent",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Extent van de kaartlaag als [minX, minY, maxX, maxY], indien van toepassing in WGS84",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    min_zoom = models.IntegerField(
        verbose_name="min zoom",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Minimale zoomniveau voor de kaartlaag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    max_zoom = models.IntegerField(
        verbose_name="max zoom",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Maximale zoomniveau voor de kaartlaag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    license = models.TextStringField(
        verbose_name="licentie",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Licentie van de kaartlaag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    refresh_interval = models.IntegerField(
        verbose_name="verversingsinterval",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Verversingsinterval in minuten voor de kaartlaag, indien van toepassing",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_layer"
        verbose_name = "kaartlaag"
        verbose_name_plural = "kaartlagen"

    class TableDescription:
        section = section_maps
        order = 4
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
