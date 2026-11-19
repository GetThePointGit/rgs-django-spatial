"""Organisatie-scope van kaartlagen, -bronnen, -thema's, stijlen en kleurensets.

Lagen, bronnen en thema's sinds waterworks-ui#219; stijlen, kleurensets en de
stijlkoppeling (``spatial_layer_style``) sinds urbanworks#433.

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
- staf (``sys_adm`` en hoger) muteert alles, zonder rijfilter (behalve het app-rijfilter
  op bron en laag, zie hieronder). Een expliciete
  ``sys_adm``-regel is nodig, anders erft staf de ``org_adm``-regel (zelfde
  patroon als ``NoteIcon`` in waterworks);
- **app-rijen** (``spatial_source`` en ``spatial_layer``, urbanworks#252) mogen door
  geen enkele rol, ook staf niet, worden gewijzigd of verwijderd: de update- en
  delete-filters van elke rol krijgen er :func:`~rgs_django_spatial.app_lagen.geen_app_rij`
  bij (zie ``app_kolom`` in :func:`scoped_table_permissions`).

Stijlkoppelingen (urbanworks#433) hebben een **eigen** scope: een organisatie
mag een eigen koppelrij op een applicatiebrede laag hangen (een eigen stijl, of
een variant die een standaardstijl vervangt). Zie
:mod:`rgs_django_spatial.models.spatial_layer_style`.

Projectniveau (waterworks#548)
------------------------------
Een rij kan ook bij **één project** horen: ``access_through = project`` met het
project-id in ``access_id``. Het pakket kent het projectmodel, de projectrollen en
de rechtentabel van de consumer niet; de standaardrechten hierboven geven op
projectrijen daarom alleen staf toegang. De consumer vult de rest in:

- ``SPATIAL_PERMISSIONS_HOOK`` (pad naar een callable ``tabel -> {rol: {actie:
  filter}}``) voegt per tabel rollen met een eigen lees- en schrijffilter toe,
  zie :func:`scoped_table_permissions`;
- ``SPATIAL_EXTRA_SCHRIJFROLLEN`` (lijst rolnamen) geeft die rollen op de
  scope-kolommen dezelfde kolomrechten als ``org_adm``, zie :func:`scope_fperm`.

Zonder deze settings verandert er niets.

Bron, laag en thema hebben daarnaast ``zichtbaarheid`` (alleen van betekenis bij
scope organisatie): ``organisatie_leden`` of ``organisatie_projecten`` (ook wie
een project van die organisatie mag lezen). Ook die regel dwingt de consumer af,
via de hook en de resolver van :mod:`rgs_django_spatial.access`.
"""

from django.conf import settings
from django.utils.module_loading import import_string
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from ..app_lagen import en_geen_app_rij
from .enums.map_zichtbaarheid import EnumMapZichtbaarheid

SCOPES_MET_ID = (EnumAccessThrough.ORGANISATION, EnumAccessThrough.PROJECT)
"""Scopes waarbij ``access_id`` gevuld is (organisatie-id of project-id)."""

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


def extra_schrijfrollen() -> tuple[str, ...]:
    """Geef de rollen van de consumer die scope-kolommen mogen schrijven.

    Returns
    -------
    tuple of str
        De setting ``SPATIAL_EXTRA_SCHRIJFROLLEN`` (standaard leeg), bv.
        ``("proj_man",)`` voor een projectbeheerder die projectrijen beheert.
    """
    return tuple(getattr(settings, "SPATIAL_EXTRA_SCHRIJFROLLEN", ()))


def scope_fperm(public: str = "---", **rollen: str) -> models.FPerm:
    """Maak kolomrechten waarin de extra schrijfrollen ``org_adm`` volgen.

    Voor kolommen die ``org_adm`` ruimer mag schrijven dan ``auth`` (de
    scope-kolommen, ``vervangt``, de authenticatieconfiguratie van een bron).
    Een rol uit ``SPATIAL_EXTRA_SCHRIJFROLLEN`` zou via ``PERMISSION_TREE``
    anders het smallere masker van ``auth`` erven.

    Parameters
    ----------
    public : str, optional
        Masker voor rollen zonder eigen regel. Standaard ``'---'``.
    **rollen : str
        Masker per rol, als bij ``FPerm``.

    Returns
    -------
    FPerm
        De kolomrechten, met voor elke extra schrijfrol zonder eigen masker het
        masker van ``org_adm``.
    """
    if "org_adm" in rollen:
        for rol in extra_schrijfrollen():
            rollen.setdefault(rol, rollen["org_adm"])
    return models.FPerm(public, **rollen)


def _rechten_van_consumer(tabel: str | None) -> dict[str, dict]:
    """Vraag de consumer om extra rollen voor één tabel.

    Parameters
    ----------
    tabel : str or None
        Tabelnaam (``db_table``); ``None`` slaat de hook over.

    Returns
    -------
    dict of str to dict
        ``{rol: {actie: filter}}`` uit ``SPATIAL_PERMISSIONS_HOOK``; leeg als de
        setting ontbreekt.

    Raises
    ------
    ImportError
        Als het ingestelde pad niet te importeren is.
    """
    pad = getattr(settings, "SPATIAL_PERMISSIONS_HOOK", None)
    if not pad or tabel is None:
        return {}
    return dict(import_string(pad)(tabel) or {})


def scoped_table_permissions(
    scope_filter: dict,
    org_adm_select: dict | None = None,
    read_filter: dict | None = None,
    app_kolom: str | None = None,
    org_adm_insert: dict | None = None,
    tabel: str | None = None,
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
    org_adm_insert : dict, optional
        Afwijkende insert-check voor ``org_adm``. Standaard ``scope_filter``.
    tabel : str, optional
        Tabelnaam (``db_table``). Daarmee wordt ``SPATIAL_PERMISSIONS_HOOK``
        geraadpleegd: een callable ``tabel -> {rol: {actie: filter}}`` van de
        consumer. Elke rol die hij teruggeeft vervangt de regel van die rol
        hieronder (of voegt de rol toe); zo krijgen projectrollen hun eigen
        lees- en schrijffilter (waterworks#548). Het app-rijfilter
        (``app_kolom``) komt ook op hun update en delete. Zonder setting
        verandert er niets.

    Returns
    -------
    TPerm
        ``auth`` leest alles, ``org_adm`` muteert binnen de scope, ``sys_adm``
        (en staf erboven) muteert alles, zonder rijfilter; alleen bij bron en
        laag (``app_kolom``) geldt het app-rijfilter voor update en delete.
    """

    def beschermd(filter_: dict) -> dict:
        return en_geen_app_rij(filter_, app_kolom) if app_kolom else filter_

    org_adm = {
        "insert": scope_filter if org_adm_insert is None else org_adm_insert,
        "update": beschermd(scope_filter),
        "delete": beschermd(scope_filter),
    }
    if org_adm_select is not None:
        org_adm["select"] = org_adm_select
    rechten = {
        "auth": {"select": read_filter if (read_filter is not None and lezen_beperkt()) else {}},
        "org_adm": org_adm,
        "sys_adm": {"select": {}, "insert": {}, "update": beschermd({}), "delete": beschermd({})},
    }
    for rol, acties in _rechten_van_consumer(tabel).items():
        acties = dict(acties)
        for actie in ("update", "delete"):
            if actie in acties:
                acties[actie] = beschermd(acties[actie])
        rechten[rol] = acties
    return models.TPerm(public=None, **rechten)


def access_through_field(doc_short: str) -> models.ForeignKey:
    """Maak het ``access_through``-veld (applicatiebreed, organisatie of project).

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
            permissions=scope_fperm("---", auth="-s-", org_adm="is-", sys_adm="isu"),
        ),
    )


def access_id_field(doc_short: str) -> models.IntegerField:
    """Maak het ``access_id``-veld (organisatie-id of project-id, naar de scope).

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
            permissions=scope_fperm("---", auth="-s-", org_adm="is-", sys_adm="isu"),
        ),
    )


def zichtbaarheid_field() -> models.ForeignKey:
    """Maak het veld ``zichtbaarheid`` van bron, laag en thema.

    Returns
    -------
    ForeignKey
        FK naar ``EnumMapZichtbaarheid`` met default ``organisatie_projecten``
        (ook in de database). Alleen van betekenis bij scope organisatie.
        ``org_adm`` en staf mogen hem zetten en wijzigen.
    """
    return models.ForeignKey(
        EnumMapZichtbaarheid,
        on_delete=models.PROTECT,
        default=EnumMapZichtbaarheid.ORGANISATIE_PROJECTEN,
        db_default=EnumMapZichtbaarheid.ORGANISATIE_PROJECTEN,
        verbose_name="zichtbaarheid",
        related_name="+",
        config=models.Config(
            doc_short=(
                "Wie een rij van een organisatie ziet: alleen de leden, of ook wie een project "
                "van die organisatie mag lezen. Zonder betekenis bij een andere scope"
            ),
            permissions=models.FPerm("---", auth="-s-", org_adm="isu", sys_adm="isu"),
        ),
    )


def unique_name_per_scope(table: str) -> models.UniqueConstraint:
    """Naam uniek binnen één scope (applicatiebreed, per organisatie of per project).

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
