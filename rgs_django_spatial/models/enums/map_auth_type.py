from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models.enums import BaseEnumExtended

from ._enum_sections import section_enum_maps


class EnumMapAuthType(BaseEnumExtended):
    NO_AUTH = "no_auth"
    BASIC_AUTH = "basic_auth"
    TOKEN = "token"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"

    config_fields = models.ArrayField(models.TextStringField())

    class Meta:
        db_table = "enum_map_auth_type"
        verbose_name = "map authentication type"
        verbose_name_plural = "map authentication types"

    class TableDescription:
        section = section_enum_maps
        modules = "*"

    @classmethod
    def default_records(cls):
        return {
            "fields": ["id", "name", "config_fields"],
            "data": [
                (cls.NO_AUTH, "geen", []),
                (cls.BASIC_AUTH, "basic auth", ["username", "password"]),
                (cls.TOKEN, "token (jwt)", ["token"]),
                (cls.API_KEY, "api key", ["key", "in", "name"]),
                (cls.OAUTH2, "oauth2", ["client_id", "client_secret", "token_url", "scopes"]),
            ],
        }
