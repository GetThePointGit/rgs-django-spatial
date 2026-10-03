"""Pluggable toegangsregeling voor de kaartbron-routes (algemeen of van één eigenaar).

Het pakket kent het organisatiemodel van de consumer niet. Een rij (bron, laag,
thema, ...) is **algemeen** (``access_through = authenticated``) of hoort bij
**één eigenaar** (``access_through = organisation``, ``access_id`` = id van die
eigenaar). Wie wat mag, bepaalt de consumer met een callable die in de settings
staat::

    SPATIAL_ACCESS_RESOLVER = "mijnapp.spatial.toegang"

De callable krijgt het ``HttpRequest`` en geeft een :class:`SpatialAccess` terug
(of laat een ``ninja.errors.HttpError`` los, bv. 403 zonder actieve organisatie).

Zonder ``SPATIAL_ACCESS_RESOLVER`` is er geen beperking: het gedrag van vóór deze
module. Zo blijven bestaande consumers ongewijzigd werken.

Hasura-kant (zelfde besluit, andere laag): ``SPATIAL_RESTRICT_READ = True`` in de
settings laat de select-permissies alleen algemene rijen en rijen van de
**actieve** organisatie (``x-hasura-org-id``) tonen; zie ``models/_scope.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Q
from django.utils.module_loading import import_string

ALGEMEEN = "authenticated"
EIGENAAR = "organisation"


@dataclass(frozen=True)
class SpatialAccess:
    """Wat één verzoek mag lezen en schrijven.

    Algemene rijen zijn altijd leesbaar. Schrijven vereist dat de rij ook
    leesbaar is: een eigenaar die je niet mag zien, mag je ook niet wijzigen.

    Parameters
    ----------
    lees_org_ids : frozenset of int
        Eigenaars wier rijen (naast de algemene) leesbaar zijn.
    schrijf_org_ids : frozenset of int
        Eigenaars wier rijen schrijfbaar zijn.
    schrijf_algemeen : bool
        Mag de gebruiker algemene rijen wijzigen (typisch: alleen staf).
    """

    lees_org_ids: frozenset[int] = frozenset()
    schrijf_org_ids: frozenset[int] = frozenset()
    schrijf_algemeen: bool = False

    def mag_lezen(self, obj) -> bool:
        """Mag deze rij gelezen worden?

        Parameters
        ----------
        obj : object
            Rij met ``access_through_id`` en ``access_id``.

        Returns
        -------
        bool
            ``True`` voor algemene rijen en rijen van een leesbare eigenaar.
        """
        if obj.access_through_id == ALGEMEEN:
            return True
        return obj.access_through_id == EIGENAAR and obj.access_id in self.lees_org_ids

    def mag_schrijven(self, obj) -> bool:
        """Mag deze rij gewijzigd worden?

        Parameters
        ----------
        obj : object
            Rij met ``access_through_id`` en ``access_id``.

        Returns
        -------
        bool
            ``True`` als de rij leesbaar is én (algemeen en ``schrijf_algemeen``,
            of van een schrijfbare eigenaar).
        """
        if not self.mag_lezen(obj):
            return False
        if obj.access_through_id == ALGEMEEN:
            return self.schrijf_algemeen
        return obj.access_id in self.schrijf_org_ids

    def kan_schrijven(self) -> bool:
        """Mag deze gebruiker überhaupt iets schrijven?

        Returns
        -------
        bool
            ``True`` bij algemeen schrijfrecht of minstens één schrijfbare eigenaar.
        """
        return self.schrijf_algemeen or bool(self.schrijf_org_ids)

    def lees_filter(self) -> Q:
        """Geef het queryset-filter voor de leesbare rijen.

        Returns
        -------
        django.db.models.Q
            Algemeen, of van een leesbare eigenaar.
        """
        return Q(access_through_id=ALGEMEEN) | Q(access_through_id=EIGENAAR, access_id__in=self.lees_org_ids)


def get_access(request) -> SpatialAccess | None:
    """Vraag de geconfigureerde resolver wat dit verzoek mag.

    Parameters
    ----------
    request : django.http.HttpRequest
        Het verzoek.

    Returns
    -------
    SpatialAccess or None
        ``None`` als ``SPATIAL_ACCESS_RESOLVER`` niet is ingesteld (onbeperkt).

    Raises
    ------
    ImportError
        Als het ingestelde pad niet te importeren is; een kapotte configuratie
        mag nooit stilletjes terugvallen op "alles mag".
    """
    pad = getattr(settings, "SPATIAL_ACCESS_RESOLVER", None)
    if not pad:
        return None
    return import_string(pad)(request)
