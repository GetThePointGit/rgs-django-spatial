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


def _lege_lijst() -> list:
    """Django-default voor ``categorieen`` (korte Returns-sectie, Google-stijl —
    zo staat ``[tool.ruff.lint.pydocstyle] convention`` in dit project).

    Bewust een eigen functie i.p.v. ``list``: rgs_django_utils'
    install_db_defaults_and_relation_cascading() behandelt ``default is list``
    als integer-ArrayField en zet dan ``array[]::integer[]``, wat op jsonb faalt.

    Returns:
        Een lege lijst.
    """
    return []


class SpatialKleurenset(models.Model):
    """Gedeelde set categorie-kleuren (bv. baggerklasse) die door meerdere stijlen wordt gebruikt.

    Een stijl-as met modus ``kleurenset`` verwijst via ``kleurensetId`` (uuid) naar dit record;
    de lib compileert de categorieën dan als een gewone categorie-as (spec §2).
    """

    # Django-default (ORM) én DB-default (Hasura insert zonder id) — zie spec §4.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=_gen_random_uuid(),
        editable=False,
        config=models.Config(permissions=models.FPerm(auth="is-")),
    )
    name = models.CharField(
        max_length=200,
        verbose_name="naam",
        config=models.Config(
            doc_short="Naam van de kleurenset",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    notes = models.TextField(
        verbose_name="opmerkingen",
        null=True,
        blank=True,
        config=models.Config(
            doc_short="Opmerkingen bij de kleurenset",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )
    # Django-default (`_lege_lijst`, ORM — o.a. een onopgeslagen instantie heeft
    # meteen `categorieen == []` i.p.v. het `DatabaseDefault`-sentinel dat
    # `db_default` alleen zou geven) én db_default (Hasura insert zonder
    # categorieen). `_lege_lijst` is bewust géén `list` en géén lambda: `list`
    # triggert in rgs_django_utils' install_db_defaults_and_relation_cascading()
    # de `default is list`-tak (bedoeld voor een integer-ArrayField), die dan een
    # `array[]::integer[]`-default op deze jsonb-kolom probeert te zetten en
    # faalt; een lambda kan `makemigrations` niet serialiseren.
    categorieen = models.JSONField(
        verbose_name="categorieën",
        default=_lege_lijst,
        db_default=[],
        config=models.Config(
            doc_short="Lijst van { waarde, label, kleur }",
            permissions=models.FPerm("---", auth="isu"),
        ),
    )

    class Meta:
        db_table = "spatial_kleurenset"
        verbose_name = "kleurenset"
        verbose_name_plural = "kleurensets"
        ordering = ["name"]

    class TableDescription:
        section = section_maps
        order = 8
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
