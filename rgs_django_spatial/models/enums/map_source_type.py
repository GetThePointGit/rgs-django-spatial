from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_maps


class EnumMapSourceType(BaseEnumExtended):
    INTERNAL = "internal"
    GEOJSON = "geojson"
    VECTOR_TILE = "vector_tile"
    WMS = "wms"
    WMS_SINGLE_TILE = "wms_single_tile"
    IMAGE = "image"
    WMTS = "wmts"
    WFS = "wfs"
    XYZ_TILE = "xyz_tile"

    config_fields = models.ArrayField(models.TextStringField())

    class Meta:
        db_table = "enum_map_source_type"
        verbose_name = "map source type"
        verbose_name_plural = "map source types"

    class TableDescription:
        section = section_enum_maps
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "config_fields"],
            "data": [
                (cls.INTERNAL, "intern", ["internal_id"]),
                (cls.GEOJSON, "GeoJSON", ["url", "params"]),
                (cls.VECTOR_TILE, "vector tile", ["url", "params", "detail_url", "id_field"]),
                (cls.WMS, "WMS", ["url", "params"]),
                (cls.WMS_SINGLE_TILE, "WMS single tile", ["url", "params"]),
                (cls.IMAGE, "image", ["url", "params", "bounds"]),
                (cls.WMTS, "WMTS", ["url", "params"]),
                (cls.WFS, "WFS", ["url", "params"]),
                (cls.XYZ_TILE, "XYZ tile", ["url", "params"]),
            ],
        }
