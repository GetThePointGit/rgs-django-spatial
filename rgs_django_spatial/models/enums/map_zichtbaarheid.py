from rgs_django_utils.database.base_models.enums import BaseEnum

from ._enum_sections import section_enum_maps


class EnumMapZichtbaarheid(BaseEnum):
    """Wie een kaartbron, -laag of -thema van een organisatie ziet (waterworks#548).

    Alleen van betekenis bij ``access_through = organisation``.
    """

    ORGANISATIE_LEDEN = "organisatie_leden"
    ORGANISATIE_PROJECTEN = "organisatie_projecten"

    class Meta:
        db_table = "enum_map_zichtbaarheid"
        verbose_name = "zichtbaarheid kaartlaag"
        verbose_name_plural = "zichtbaarheid kaartlagen"

    class TableDescription:
        section = section_enum_maps
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name"],
            "data": [
                (cls.ORGANISATIE_LEDEN, "Alleen leden van de organisatie"),
                (cls.ORGANISATIE_PROJECTEN, "Ook deelnemers aan projecten van de organisatie"),
            ],
        }
