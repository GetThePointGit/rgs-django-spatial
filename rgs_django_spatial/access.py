"""Pluggable toegangsregeling voor de kaartbron-routes (algemeen of van één eigenaar).

Het pakket kent het organisatie- en projectmodel van de consumer niet. Een rij
(bron, laag, thema, ...) is **algemeen** (``access_through = authenticated``),
hoort bij **één eigenaar** (``access_through = organisation``, ``access_id`` = id
van die eigenaar) of bij **één project** (``access_through = project``,
``access_id`` = project-id, waterworks#548). Wie wat mag, bepaalt de consumer met
een callable die in de settings staat::

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
PROJECT = "project"
ORGANISATIE_PROJECTEN = "organisatie_projecten"
_CACHE_ATTR = "_spatial_access"


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
    lees_alles : bool
        Leest alle rijen, van elke eigenaar (typisch: staf).
    schrijf_alles : bool
        Schrijft elke leesbare rij, van elke eigenaar (typisch: staf).
    lees_project_ids : frozenset of int
        Projecten wier rijen leesbaar zijn.
    schrijf_project_ids : frozenset of int
        Projecten wier rijen schrijfbaar zijn (typisch: projectbeheerder).
    lees_org_ids_via_project : frozenset of int
        Eigenaars van wie de gebruiker een project mag lezen zonder er lid van
        te zijn. Van hen zijn alleen de rijen met ``zichtbaarheid =
        organisatie_projecten`` leesbaar; een rij zonder dat veld (stijl,
        kleurenset) telt als ``organisatie_projecten``.
    """

    lees_org_ids: frozenset[int] = frozenset()
    schrijf_org_ids: frozenset[int] = frozenset()
    schrijf_algemeen: bool = False
    lees_alles: bool = False
    schrijf_alles: bool = False
    lees_project_ids: frozenset[int] = frozenset()
    schrijf_project_ids: frozenset[int] = frozenset()
    lees_org_ids_via_project: frozenset[int] = frozenset()

    def mag_lezen(self, obj) -> bool:
        """Mag deze rij gelezen worden?

        Parameters
        ----------
        obj : object
            Rij met ``access_through_id`` en ``access_id``.

        Returns
        -------
        bool
            ``True`` voor algemene rijen, rijen van een leesbare eigenaar of een
            leesbaar project, en rijen met ``organisatie_projecten`` van een
            eigenaar uit ``lees_org_ids_via_project``.
        """
        if self.lees_alles or obj.access_through_id == ALGEMEEN:
            return True
        if obj.access_through_id == PROJECT:
            return obj.access_id in self.lees_project_ids
        if obj.access_through_id != EIGENAAR:
            return False
        if obj.access_id in self.lees_org_ids:
            return True
        zichtbaarheid = getattr(obj, "zichtbaarheid_id", ORGANISATIE_PROJECTEN)
        return obj.access_id in self.lees_org_ids_via_project and zichtbaarheid == ORGANISATIE_PROJECTEN

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
            of van een schrijfbare eigenaar, of van een schrijfbaar project).
        """
        if not self.mag_lezen(obj):
            return False
        if self.schrijf_alles:
            return True
        if obj.access_through_id == ALGEMEEN:
            return self.schrijf_algemeen
        if obj.access_through_id == PROJECT:
            return obj.access_id in self.schrijf_project_ids
        return obj.access_id in self.schrijf_org_ids

    def kan_schrijven(self) -> bool:
        """Mag deze gebruiker überhaupt iets schrijven?

        Returns
        -------
        bool
            ``True`` bij algemeen schrijfrecht of minstens één schrijfbare
            eigenaar of schrijfbaar project.
        """
        return (
            self.schrijf_alles or self.schrijf_algemeen or bool(self.schrijf_org_ids) or bool(self.schrijf_project_ids)
        )

    def lees_filter(self, met_zichtbaarheid: bool = True) -> Q:
        """Geef het queryset-filter voor de leesbare rijen.

        Parameters
        ----------
        met_zichtbaarheid : bool, optional
            Heeft het model het veld ``zichtbaarheid`` (bron, laag, thema)?
            Zo niet, dan tellen alle rijen van een eigenaar uit
            ``lees_org_ids_via_project`` als leesbaar. Standaard ``True``.

        Returns
        -------
        django.db.models.Q
            Algemeen, van een leesbare eigenaar of een leesbaar project, of met
            ``organisatie_projecten`` van een eigenaar uit
            ``lees_org_ids_via_project``; bij ``lees_alles`` alles.
        """
        if self.lees_alles:
            return Q()
        filter_ = Q(access_through_id=ALGEMEEN) | Q(access_through_id=EIGENAAR, access_id__in=self.lees_org_ids)
        if self.lees_project_ids:
            filter_ |= Q(access_through_id=PROJECT, access_id__in=self.lees_project_ids)
        if self.lees_org_ids_via_project:
            via_project = Q(access_through_id=EIGENAAR, access_id__in=self.lees_org_ids_via_project)
            if met_zichtbaarheid:
                via_project &= Q(zichtbaarheid_id=ORGANISATIE_PROJECTEN)
            filter_ |= via_project
        return filter_


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
        Het resultaat wordt per verzoek onthouden; een ``HttpError`` van de
        resolver wordt niet onthouden en komt bij elke aanroep opnieuw.

    Raises
    ------
    ImportError
        Als het ingestelde pad niet te importeren is; een kapotte configuratie
        mag nooit stilletjes terugvallen op "alles mag".
    """
    pad = getattr(settings, "SPATIAL_ACCESS_RESOLVER", None)
    if not pad:
        return None
    # Eén keer per verzoek: de resolver doet in de praktijk databasequery's en
    # een route roept dit voor lezen én schrijven aan.
    if not hasattr(request, _CACHE_ATTR):
        setattr(request, _CACHE_ATTR, import_string(pad)(request))
    return getattr(request, _CACHE_ATTR)
