import uuid

from django.db.models import Func
from rgs_django_utils.database import dj_extended_models as models

from ._scope import (
    LEES_SCOPE_FILTER,
    ORG_SCOPE_FILTER,
    access_id_field,
    access_through_field,
    scoped_table_permissions,
)
from ._sections import section_maps


def _gen_random_uuid() -> Func:
    """Bouwt de db_default-expressie ``gen_random_uuid()`` (Postgres, spec §4).

    ``Func(function=...)`` legt de functienaam alleen vast in ``extra`` (gebruikt
    door ``as_sql``), niet als attribuut. We zetten ``.function`` hier expliciet
    zodat de default ook via dat attribuut inspecteerbaar is (bewaakt door
    ``tests/test_spatial_kleurenset.py::test_migratie_0007_zet_db_default_gen_random_uuid``).
    """
    func = Func(function="gen_random_uuid")
    func.function = "gen_random_uuid"
    return func


class SpatialStyle(models.Model):
    """Mapbox stijl voor gebruik in lagen."""

    # Uuid-pk (spec §4): Django-default voor de ORM, DB-default voor Hasura-inserts
    # zonder id. De frontend-upsert conflicteert op spatial_style_pkey en stuurt
    # zelf een uuid mee, dus 'id' moet in de insert_input zitten (auth="is-").
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=_gen_random_uuid(),
        editable=False,
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

    # Scope (urbanworks#433): applicatiebreed of van één organisatie.
    access_through = access_through_field("Bereik van de stijl: applicatiebreed, één organisatie of één project")
    access_id = access_id_field("Organisatie- of project-id als de stijl van één organisatie of project is")

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
        # Scope als bij laag, bron en thema (urbanworks#433, rgs-django-spatial#17):
        # org_adm muteert alleen stijlen van de actieve organisatie, staf alles.
        # `auth` behoudt select; met SPATIAL_RESTRICT_READ alleen applicatiebreed
        # plus de actieve organisatie.
        return scoped_table_permissions(ORG_SCOPE_FILTER, read_filter=LEES_SCOPE_FILTER, tabel=cls._meta.db_table)
