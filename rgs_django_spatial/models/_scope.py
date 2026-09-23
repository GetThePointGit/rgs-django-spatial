"""Organisatie-scope van kaartlagen, -bronnen en -thema's (waterworks-ui#219).

Een rij is **applicatiebreed** (``access_through = authenticated``,
``access_id`` leeg) of hoort bij **één organisatie** (``access_through =
organisation``, ``access_id`` = organisatie-id). Bestaande rijen zijn
applicatiebreed via de DB-default, zodat er bij de invoering niets verdwijnt.

Rechten (Hasura):

- iedere ingelogde gebruiker (``auth``) leest alles; het afschermen van het
  lezen volgt in een vervolgticket (waterworks#548);
- ``org_adm`` muteert alleen rijen van de **actieve** organisatie
  (``x-hasura-org-id``) en maakt alleen zulke rijen aan. De client stuurt de
  scope mee; de insert-check dwingt hem af. Een preset kan hier niet: presets
  erven via ``PERMISSION_TREE`` door naar ``sys_adm``, en staf zonder
  organisatiecontext heeft geen ``x-hasura-org-id``;
- staf (``sys_adm`` en hoger) muteert alles, zonder rijfilter. Een expliciete
  ``sys_adm``-regel is nodig, anders erft staf de ``org_adm``-regel (zelfde
  patroon als ``NoteIcon`` in waterworks).
"""

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

ORG_SCOPE_FILTER = {
    "access_through_id": {"_eq": EnumAccessThrough.ORGANISATION},
    "access_id": {"_eq": "x-hasura-org-id"},
}
"""Rijfilter: de rij hoort bij de actieve organisatie van de gebruiker."""


def scoped_table_permissions(scope_filter: dict, org_adm_select: dict | None = None) -> models.TPerm:
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
        de brede select van ``auth``.

    Returns
    -------
    TPerm
        ``auth`` leest alles, ``org_adm`` muteert binnen de scope, ``sys_adm``
        (en staf erboven) muteert alles.
    """
    org_adm = {"insert": scope_filter, "update": scope_filter, "delete": scope_filter}
    if org_adm_select is not None:
        org_adm["select"] = org_adm_select
    return models.TPerm(
        public=None,
        auth={"select": {}},
        org_adm=org_adm,
        sys_adm={"select": {}, "insert": {}, "update": {}, "delete": {}},
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
