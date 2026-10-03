import uuid

from django.db.models import Func
from rgs_django_utils.database import dj_extended_models as models

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
        # Mutaties zijn beheer: alleen org_adm (en staf hoger in de rolketen
        # sys_adm/dev/dev_man) mag stijlen aanmaken/wijzigen/verwijderen.
        # `auth` behoudt select. Zie GetThePointGit/rgs-django-spatial#1.
        no_filt = {}

        return models.TPerm(
            public=None,
            auth={
                "select": no_filt,
            },
            org_adm={
                "insert": no_filt,
                "update": no_filt,
                "delete": no_filt,
            },
        )
