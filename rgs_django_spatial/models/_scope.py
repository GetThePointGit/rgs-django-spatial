"""Organisatie-scope van kaartlagen, -bronnen en -thema's (waterworks-ui#219).

Een rij is **applicatiebreed** (``access_through = authenticated``,
``access_id`` leeg) of hoort bij **één organisatie** (``access_through =
organisation``, ``access_id`` = organisatie-id). Bestaande rijen zijn
applicatiebreed via de DB-default, zodat er bij de invoering niets verdwijnt.

Rechten (Hasura):

- iedere ingelogde gebruiker (``auth``) leest standaard alles. Met
  ``SPATIAL_RESTRICT_READ = True`` in de settings van de consumer leest hij alleen
  applicatiebrede rijen en rijen van de **actieve** organisatie
  (:data:`LEES_SCOPE_FILTER`, urbanworks#208);
- ``org_adm`` muteert alleen rijen van de **actieve** organisatie
  (``x-hasura-org-id``) en maakt alleen zulke rijen aan. De client stuurt de
  scope mee; de insert-check dwingt hem af. Een preset kan hier niet: presets
  erven via ``PERMISSION_TREE`` door naar ``sys_adm``, en staf zonder
  organisatiecontext heeft geen ``x-hasura-org-id``;
- staf (``sys_adm`` en hoger) muteert alles, zonder rijfilter. Een expliciete
  ``sys_adm``-regel is nodig, anders erft staf de ``org_adm``-regel (zelfde
  patroon als ``NoteIcon`` in waterworks);
- **app-rijen** (``spatial_source`` en ``spatial_layer``, urbanworks#252) mogen door
  geen enkele rol, ook staf niet, worden gewijzigd of verwijderd: de update- en
  delete-filters van elke rol krijgen er :func:`~rgs_django_spatial.app_lagen.geen_app_rij`
  bij (zie ``app_kolom`` in :func:`scoped_table_permissions`).
"""

from django.conf import settings
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from ..app_lagen import en_geen_app_rij

ORG_SCOPE_FILTER = {
    "access_through_id": {"_eq": EnumAccessThrough.ORGANISATION},
    "access_id": {"_eq": "x-hasura-org-id"},
}
"""Rijfilter: de rij hoort bij de actieve organisatie van de gebruiker."""

LEES_SCOPE_FILTER = {
    "_or": [
        {"access_through_id": {"_eq": EnumAccessThrough.AUTHENTICATED}},
        ORG_SCOPE_FILTER,
    ]
}
"""Rijfilter om te lezen: de rij is applicatiebreed, of van de actieve organisatie."""


def lezen_beperkt() -> bool:
    """Is lezen beperkt tot algemene rijen en die van de actieve organisatie?

    Returns
    -------
    bool
        De setting ``SPATIAL_RESTRICT_READ`` (standaard ``False``: lezen is breed).
    """
    return bool(getattr(settings, "SPATIAL_RESTRICT_READ", False))


def scoped_table_permissions(
    scope_filter: dict,
    org_adm_select: dict | None = None,
    read_filter: dict | None = None,
    app_kolom: str | None = None,
) -> models.TPerm:
    """Bouw de tabelpermissies voor een tabel met organisatie-scope.

    Parameters
    ----------
    scope_filter : dict
        Hasura-rijfilter dat een rij aan de actieve organisatie koppelt:
        :data:`ORG_SCOPE_FILTER` voor de scope-tabellen zelf, of een filter
        via een relatie (bv. ``{"layer": ORG_SCOPE_FILTER}``) voor
        koppeltabellen.
    org_adm_select : dict, optional
        Afwijkend select-filter voor ``org_adm``. Standaard erft ``org_adm``
        de select van ``auth``.
    read_filter : dict, optional
        Select-filter voor ``auth`` (en wie dat erft) als lezen beperkt is
        (``SPATIAL_RESTRICT_READ``): :data:`LEES_SCOPE_FILTER`, of via een
        relatie (bv. ``{"layer": LEES_SCOPE_FILTER}``) voor koppeltabellen.
        Staf houdt een select zonder filter.
    app_kolom : str, optional
        JSON-kolom die app-rijen markeert (``source_config`` of ``params``).
        Dan wordt "geen app-rij" met EN aan update en delete van elke rol
        gekoppeld (ook ``sys_adm``). Select en insert blijven gelijk.

    Returns
    -------
    TPerm
        ``auth`` leest alles, ``org_adm`` muteert binnen de scope, ``sys_adm``
        (en staf erboven) muteert alles.
    """

    def beschermd(filter_: dict) -> dict:
        return en_geen_app_rij(filter_, app_kolom) if app_kolom else filter_

    org_adm = {"insert": scope_filter, "update": beschermd(scope_filter), "delete": beschermd(scope_filter)}
    if org_adm_select is not None:
        org_adm["select"] = org_adm_select
    return models.TPerm(
        public=None,
        auth={"select": read_filter if (read_filter is not None and lezen_beperkt()) else {}},
        org_adm=org_adm,
        sys_adm={"select": {}, "insert": {}, "update": beschermd({}), "delete": beschermd({})},
    )


def access_through_field(doc_short: str) -> models.ForeignKey:
    """Maak het ``access_through``-veld (applicatiebreed of organisatie).

    Parameters
    ----------
    doc_short : str
        Korte omschrijving voor de documentatie en het JSON-schema.

    Returns
    -------
    ForeignKey
        FK naar ``EnumAccessThrough`` met default ``authenticated`` (ook in de
        database, zodat een Hasura-insert zonder scope applicatiebreed wordt).
        ``org_adm`` mag hem bij aanmaken zetten, alleen staf mag hem wijzigen.
    """
    return models.ForeignKey(
        EnumAccessThrough,
        on_delete=models.PROTECT,
        default=EnumAccessThrough.AUTHENTICATED,
        db_default=EnumAccessThrough.AUTHENTICATED,
        verbose_name="toegang via",
        config=models.Config(
            doc_short=doc_short,
            permissions=models.FPerm("---", auth="-s-", org_adm="is-", sys_adm="isu"),
        ),
    )


def access_id_field(doc_short: str) -> models.IntegerField:
    """Maak het ``access_id``-veld (organisatie-id bij organisatie-scope).

    Parameters
    ----------
    doc_short : str
        Korte omschrijving voor de documentatie en het JSON-schema.

    Returns
    -------
    IntegerField
        Nullable id; leeg bij applicatiebrede rijen. Rechten als
        :func:`access_through_field`.
    """
    return models.IntegerField(
        verbose_name="toegang id",
        null=True,
        blank=True,
        config=models.Config(
            doc_short=doc_short,
            permissions=models.FPerm("---", auth="-s-", org_adm="is-", sys_adm="isu"),
        ),
    )


def unique_name_per_scope(table: str) -> models.UniqueConstraint:
    """Naam uniek binnen één scope (applicatiebreed, of per organisatie).

    ``nulls_distinct=False`` zodat twee applicatiebrede rijen (``access_id``
    leeg) met dezelfde naam óók botsen.

    Parameters
    ----------
    table : str
        Tabelnaam, voor de constraintnaam.

    Returns
    -------
    UniqueConstraint
        Constraint op ``(name, access_through, access_id)``.
    """
    return models.UniqueConstraint(
        fields=["name", "access_through", "access_id"],
        nulls_distinct=False,
        name=f"{table}_name_per_scope",
    )
