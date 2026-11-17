"""Organisatie-kaartlagen applicatiebreed maken (waterworks-ui#219).

Staf kan een laag, bron of thema van één organisatie "upgraden" naar
applicatiebreed (zichtbaar en bruikbaar voor alle organisaties, alleen door
staf te beheren). Besluit opdrachtgever 23-09:

- een **laag** neemt haar **bron** mee: die wordt ook applicatiebreed;
- een laag neemt ook haar **stijlkoppelingen** mee, met de stijlen en de
  kleurensets waar die naar verwijzen (urbanworks#433): anders zou een
  applicatiebrede laag stijlen tonen die alleen de oude organisatie kan lezen;
- een **thema** wordt **gekopieerd**, niet verplaatst: de organisatie houdt
  haar eigen thema (en haar andere lagen erin); de geüpgradede laag komt onder
  het applicatiebrede thema met dezelfde naam, dat hergebruikt wordt als het
  al bestaat. In het lagenpaneel vallen thema's met dezelfde naam samen.

Elke functie draait in één transactie. Een naamconflict met een bestaande
applicatiebrede rij geeft een :class:`ApplicatiebreedConflict` en laat de
database ongemoeid.

Autorisatie (alleen staf) hoort bij de aanroeper: deze module kent geen
gebruikers.
"""

from __future__ import annotations

from django.db import transaction
from rgs_django_utils.models.enums.enum_access_through import EnumAccessThrough

from .models import (
    SpatialKleurenset,
    SpatialLayer,
    SpatialLayerStyle,
    SpatialMapLayer,
    SpatialSource,
    SpatialStyle,
    SpatialTheme,
)


class ApplicatiebreedConflict(ValueError):
    """Er bestaat al een applicatiebrede rij met dezelfde naam."""


def is_applicatiebreed(obj: SpatialLayer | SpatialSource | SpatialTheme) -> bool:
    """Is deze laag, bron of dit thema applicatiebreed?

    Parameters
    ----------
    obj : SpatialLayer, SpatialSource or SpatialTheme
        Rij met organisatie-scope.

    Returns
    -------
    bool
        ``True`` als ``access_through`` ``authenticated`` is.
    """
    return obj.access_through_id == EnumAccessThrough.AUTHENTICATED


def _maak_applicatiebreed(obj: SpatialLayer | SpatialSource) -> bool:
    """Zet een organisatierij om naar applicatiebreed (in de huidige transactie).

    Parameters
    ----------
    obj : SpatialLayer or SpatialSource
        De om te zetten rij.

    Returns
    -------
    bool
        ``True`` als de rij is omgezet, ``False`` als hij al applicatiebreed was.

    Raises
    ------
    ApplicatiebreedConflict
        Als er al een applicatiebrede rij met dezelfde naam bestaat.
    """
    if is_applicatiebreed(obj):
        return False
    model = type(obj)
    if model.objects.filter(name=obj.name, access_through_id=EnumAccessThrough.AUTHENTICATED).exists():
        raise ApplicatiebreedConflict(
            f"Er bestaat al een applicatiebrede {model._meta.verbose_name} '{obj.name}'. "
            "Hernoem een van beide en probeer het opnieuw."
        )
    obj.access_through_id = EnumAccessThrough.AUTHENTICATED
    obj.access_id = None
    obj.save(update_fields=["access_through", "access_id"])
    return True


def kleurenset_ids(style_config) -> set[str]:
    """Verzamel de kleurenset-id's waar een stijlconfiguratie naar verwijst.

    Parameters
    ----------
    style_config : object
        De JSON-waarde van ``spatial_style.style_config`` (willekeurig genest).

    Returns
    -------
    set of str
        Alle waarden onder een sleutel ``kleurensetId``, als tekst.
    """
    gevonden: set[str] = set()
    if isinstance(style_config, dict):
        for sleutel, waarde in style_config.items():
            if sleutel == "kleurensetId" and waarde:
                gevonden.add(str(waarde))
            else:
                gevonden |= kleurenset_ids(waarde)
    elif isinstance(style_config, list):
        for waarde in style_config:
            gevonden |= kleurenset_ids(waarde)
    return gevonden


def _stijlen_applicatiebreed(laag: SpatialLayer) -> int:
    """Maak de stijlkoppelingen van een zojuist geüpgradede laag applicatiebreed.

    De stijlen van die koppelingen en de kleurensets waar ze naar verwijzen
    gaan mee. Gebruikt een andere laag van de organisatie dezelfde stijl, dan
    verwijst die voortaan naar een applicatiebrede stijl (alleen-lezen voor de
    organisatie), net als bij een gedeelde bron.

    Parameters
    ----------
    laag : SpatialLayer
        De laag, al applicatiebreed.

    Returns
    -------
    int
        Aantal omgezette stijlkoppelingen.
    """
    algemeen = {"access_through_id": EnumAccessThrough.AUTHENTICATED, "access_id": None}
    koppelingen = SpatialLayerStyle.objects.filter(layer=laag).exclude(
        access_through_id=EnumAccessThrough.AUTHENTICATED
    )
    stijl_ids = [stijl_id for stijl_id in koppelingen.values_list("style_id", flat=True) if stijl_id]
    stijlen = SpatialStyle.objects.filter(pk__in=stijl_ids)
    sets: set[str] = set()
    for config in stijlen.values_list("style_config", flat=True):
        sets |= kleurenset_ids(config)
    # Volgorde: eerst kleurensets en stijlen, dan de koppelingen. De trigger op
    # spatial_layer_style weigert een applicatiebrede koppeling met een
    # organisatiestijl.
    SpatialKleurenset.objects.filter(pk__in=sets).update(**algemeen)
    stijlen.update(**algemeen)
    return koppelingen.update(**algemeen)


def _applicatiebreed_thema(thema: SpatialTheme) -> tuple[SpatialTheme, bool]:
    """Geef het applicatiebrede thema met dezelfde naam; maak het zo nodig aan.

    Parameters
    ----------
    thema : SpatialTheme
        Het (organisatie-)thema dat gekopieerd moet worden.

    Returns
    -------
    tuple of (SpatialTheme, bool)
        Het applicatiebrede thema en of het nieuw is aangemaakt. Is ``thema``
        zelf al applicatiebreed, dan is dat het resultaat.
    """
    if is_applicatiebreed(thema):
        return thema, False
    return SpatialTheme.objects.get_or_create(
        name=thema.name,
        access_through_id=EnumAccessThrough.AUTHENTICATED,
        access_id=None,
        defaults={"order": thema.order},
    )


@transaction.atomic
def kopieer_thema_naar_applicatiebreed(thema_id: int) -> dict:
    """Kopieer een organisatiethema naar een applicatiebreed thema.

    Het organisatiethema blijft bestaan. Bestaat er al een applicatiebreed
    thema met dezelfde naam, dan is er niets te doen.

    Parameters
    ----------
    thema_id : int
        Id van het thema.

    Returns
    -------
    dict
        ``{"thema_id": <id applicatiebreed thema>, "aangemaakt": bool}``.
    """
    thema = SpatialTheme.objects.select_for_update().get(pk=thema_id)
    kopie, aangemaakt = _applicatiebreed_thema(thema)
    return {"thema_id": kopie.pk, "aangemaakt": aangemaakt}


@transaction.atomic
def upgrade_bron_naar_applicatiebreed(bron_id: int) -> dict:
    """Maak een organisatiebron applicatiebreed.

    Lagen die de bron gebruiken blijven van hun organisatie; ze verwijzen dan
    naar een applicatiebrede bron, die hun organisatie alleen nog kan lezen.

    Parameters
    ----------
    bron_id : int
        Id van de bron.

    Returns
    -------
    dict
        ``{"bron_id": int, "omgezet": bool}``.

    Raises
    ------
    ApplicatiebreedConflict
        Als er al een applicatiebrede bron met dezelfde naam bestaat.
    """
    bron = SpatialSource.objects.select_for_update().get(pk=bron_id)
    return {"bron_id": bron.pk, "omgezet": _maak_applicatiebreed(bron)}


@transaction.atomic
def upgrade_laag_naar_applicatiebreed(laag_id: int) -> dict:
    """Maak een organisatielaag applicatiebreed, met haar bron en thema.

    - de laag wordt applicatiebreed;
    - de bron gaat mee (wordt ook applicatiebreed);
    - de stijlkoppelingen gaan mee, met hun stijlen en kleurensets;
    - voor elk organisatiethema waaronder de laag op een kaart hangt, komt de
      laag onder het applicatiebrede thema met dezelfde naam (aangemaakt als
      het nog niet bestaat). Het organisatiethema zelf blijft ongewijzigd.

    Parameters
    ----------
    laag_id : int
        Id van de laag (``spatial_layer``).

    Returns
    -------
    dict
        ``{"laag_id": int, "laag_omgezet": bool, "bron_omgezet": bool,
        "themas_aangemaakt": list[str], "stijlen_omgezet": int}``.

    Raises
    ------
    ApplicatiebreedConflict
        Als er al een applicatiebrede laag of bron met dezelfde naam bestaat.
    """
    laag = SpatialLayer.objects.select_for_update(of=("self",)).select_related("source").get(pk=laag_id)
    laag_omgezet = _maak_applicatiebreed(laag)
    bron_omgezet = _maak_applicatiebreed(laag.source)
    stijlen_omgezet = _stijlen_applicatiebreed(laag)

    themas_aangemaakt = []
    koppelingen = SpatialMapLayer.objects.select_for_update(of=("self",)).filter(layer=laag, theme__isnull=False)
    for koppeling in koppelingen.select_related("theme"):
        kopie, aangemaakt = _applicatiebreed_thema(koppeling.theme)
        if aangemaakt:
            themas_aangemaakt.append(kopie.name)
        if kopie.pk != koppeling.theme_id:
            koppeling.theme = kopie
            koppeling.save(update_fields=["theme"])

    return {
        "laag_id": laag.pk,
        "laag_omgezet": laag_omgezet,
        "bron_omgezet": bron_omgezet,
        "themas_aangemaakt": themas_aangemaakt,
        "stijlen_omgezet": stijlen_omgezet,
    }
