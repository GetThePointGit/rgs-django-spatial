"""Bescherming van app-rijen in ``spatial_source`` en ``spatial_layer`` (urbanworks#252).

Een **app-rij** is een bron of laag die de applicatie zelf beheert (bv. de laag met
alle aanvragen). Zo'n rij herken je aan de sleutel ``app_layer``: in
``SpatialSource.source_config`` voor een bron, in ``SpatialLayer.params`` voor een
laag. Een app-rij mag niet worden gewijzigd of verwijderd, door niemand.

Twee lagen van bescherming:

- **Hasura** (:func:`geen_app_rij`): Hasura omzeilt Django. De filters worden in
  ``models/_scope.py`` aan de update- en delete-rechten van elke rol gekoppeld
  (ook ``sys_adm``). Dat is de enige bescherming op dat pad.
- **Django** (:func:`controleer_voor_verwijderen`, :func:`controleer_voor_opslaan`):
  ``pre_delete``/``pre_save``-signals, aangesloten in ``apps.py``. Ze dekken ORM,
  admin en ``QuerySet.delete()`` (die per rij signals afvuurt), maar niet
  ``QuerySet.update()`` of ruwe SQL.

Seeds en migraties die zelf app-rijen aanmaken of bijwerken draaien binnen
:func:`app_laag_onderhoud`.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import PermissionDenied

APP_SLEUTEL = "app_layer"
"""JSON-sleutel die een rij als app-rij markeert."""

_onderhoud: ContextVar[bool] = ContextVar("rgs_spatial_app_laag_onderhoud", default=False)


class AppLaagBeschermd(PermissionDenied):
    """Een app-rij mag niet worden gewijzigd of verwijderd."""


def _heeft_sleutel(waarde) -> bool:
    return isinstance(waarde, dict) and APP_SLEUTEL in waarde


def is_app_laag(layer) -> bool:
    """Is deze laag een app-laag?

    Parameters
    ----------
    layer : SpatialLayer
        De laag.

    Returns
    -------
    bool
        ``True`` als ``params`` de sleutel ``app_layer`` heeft.
    """
    return _heeft_sleutel(getattr(layer, "params", None))


def is_app_bron(source) -> bool:
    """Is deze bron een app-bron?

    Parameters
    ----------
    source : SpatialSource
        De bron.

    Returns
    -------
    bool
        ``True`` als ``source_config`` de sleutel ``app_layer`` heeft.
    """
    return _heeft_sleutel(getattr(source, "source_config", None))


def geen_app_rij(kolom: str) -> dict:
    """Hasura-rijfilter: de rij is géén app-rij.

    Parameters
    ----------
    kolom : str
        De JSON-kolom met de markering (``source_config`` of ``params``).

    Returns
    -------
    dict
        Boolexp: de kolom is leeg, of heeft de sleutel ``app_layer`` niet.
    """
    return {"_or": [{kolom: {"_is_null": True}}, {"_not": {kolom: {"_has_key": APP_SLEUTEL}}}]}


def en_geen_app_rij(filter_: dict | None, kolom: str) -> dict:
    """Koppel :func:`geen_app_rij` met EN aan een bestaand rijfilter.

    Parameters
    ----------
    filter_ : dict or None
        Bestaand filter; leeg of ``{}`` betekent "geen beperking".
    kolom : str
        De JSON-kolom met de markering.

    Returns
    -------
    dict
        Alleen het app-filter als ``filter_`` leeg is, anders ``{"_and": [filter_, app-filter]}``.
    """
    app = geen_app_rij(kolom)
    if not filter_:
        return app
    return {"_and": [filter_, app]}


@contextmanager
def app_laag_onderhoud():
    """Sta wijzigen, verwijderen en aanmaken van app-rijen toe (voor seeds en migraties).

    Yields
    ------
    None
        Binnen het blok zijn de Django-guards uitgeschakeld (alleen voor deze
        thread/context). Hasura-rechten blijven gelden.
    """
    token = _onderhoud.set(True)
    try:
        yield
    finally:
        _onderhoud.reset(token)


def _is_app_rij(instance) -> bool:
    return is_app_laag(instance) if hasattr(instance, "params") else is_app_bron(instance)


def controleer_voor_verwijderen(sender, instance, **kwargs):
    """``pre_delete``-receiver: weiger het verwijderen van een app-rij.

    Parameters
    ----------
    sender : type
        ``SpatialLayer`` of ``SpatialSource``.
    instance : Model
        De te verwijderen rij.
    **kwargs
        Overige signal-argumenten (genegeerd).

    Raises
    ------
    AppLaagBeschermd
        Bij een app-rij buiten :func:`app_laag_onderhoud`.
    """
    if _onderhoud.get():
        return
    if _is_app_rij(instance):
        raise AppLaagBeschermd(f"{sender.__name__} {instance.pk} is een app-rij en kan niet worden verwijderd.")


def controleer_voor_opslaan(sender, instance, raw=False, **kwargs):
    """``pre_save``-receiver: weiger wijzigen of aanmaken van een app-rij.

    Een bestaande rij telt als app-rij op basis van de **opgeslagen** staat (zodat
    het weghalen van de markering ook geweigerd wordt), een nieuwe rij op basis
    van de instantie zelf. ``QuerySet.update()`` en ruwe SQL passeren geen
    ``pre_save`` en worden dus niet gedekt.

    Parameters
    ----------
    sender : type
        ``SpatialLayer`` of ``SpatialSource``.
    instance : Model
        De op te slaan rij.
    raw : bool
        Loaddata-modus; ook fixtures gaan bewust door de guard.
    **kwargs
        Overige signal-argumenten (genegeerd).

    Raises
    ------
    AppLaagBeschermd
        Bij het wijzigen van een bestaande app-rij of het aanmaken van een
        nieuwe buiten :func:`app_laag_onderhoud`.
    """
    if _onderhoud.get():
        return
    if _is_app_rij(instance):
        raise AppLaagBeschermd(f"{sender.__name__} {instance.pk} is een app-rij en kan niet worden gewijzigd.")
    if instance._state.adding:
        return
    kolom = "params" if hasattr(instance, "params") else "source_config"
    opgeslagen = sender._base_manager.filter(pk=instance.pk).values_list(kolom, flat=True).first()
    if _heeft_sleutel(opgeslagen):
        raise AppLaagBeschermd(f"{sender.__name__} {instance.pk} is een app-rij en kan niet worden gewijzigd.")
