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


def _lege_lijst() -> list:
    """Django-default voor ``categorieen``.

    Bewust een eigen functie i.p.v. ``list``: rgs_django_utils'
    install_db_defaults_and_relation_cascading() behandelt ``default is list``
    als integer-ArrayField en zet dan ``array[]::integer[]``, wat op jsonb faalt.

    Returns
    -------
    list
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

    # Scope (urbanworks#433): applicatiebreed of van één organisatie.
    access_through = access_through_field("Bereik van de kleurenset: applicatiebreed of één organisatie")
    access_id = access_id_field("Organisatie-id als de kleurenset van één organisatie is")

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
        # Scope als bij laag, bron en thema (urbanworks#433, rgs-django-spatial#17):
        # org_adm muteert alleen kleurensets van de actieve organisatie, staf alles.
        # `auth` behoudt select; met SPATIAL_RESTRICT_READ alleen applicatiebreed
        # plus de actieve organisatie.
        return scoped_table_permissions(ORG_SCOPE_FILTER, read_filter=LEES_SCOPE_FILTER)
