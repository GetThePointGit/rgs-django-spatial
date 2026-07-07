"""PMTiles-generatie voor SpatialSource-bronnen (bestand-upload en WFS).

Synchroon, testbaar werk in ``build_tiles_for_source``; ``start_spatial_tile_build``
draait dat in een daemon-thread. Bewust geen Celery: er is in dit project geen broker.
"""
import contextlib
import logging
import os
import tempfile
import threading

from django.db import connections
from django.utils import timezone
from osgeo import gdal

from rgs_django_spatial.tiles.pmtiles import generate_pmtiles, inspect_layers, inspect_vector
from rgs_django_spatial.tiles.storage import store_pmtiles

log = logging.getLogger(__name__)

# Brontypes waarvoor deze pijplijn tiles bouwt.
FILE_SOURCE_TYPES = {"geojson", "vector_tile"}  # bestand-upload; zie gdal_input_for_source
WFS_SOURCE_TYPE = "wfs"


@contextlib.contextmanager
def _local_copy(filefield):
    """Stream a (possibly remote/S3) media FileField to a local temp file.

    Yields the temp path and always removes it. Works for FileSystemStorage and
    S3 alike because it uses ``.open()`` (never ``.path``).
    """
    suffix = os.path.splitext(filefield.name)[1] or ".gpkg"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as out, filefield.open("rb") as src:
            for chunk in src.chunks():
                out.write(chunk)
        yield tmp
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp)


@contextlib.contextmanager
def gdal_auth_config(source):
    """Zet ``GDAL_HTTP_USERPWD`` (thread-lokaal) uit basic-auth-config en herstel bij afsluiten.

    Zorgt dat GDAL beschermde WFS/URL-bronnen kan lezen (inspecteren én tilen).
    Gebruikt de thread-lokale GDAL-config-API zodat credentials niet lekken naar
    gelijktijdige requests/threads op andere (publieke) bronnen.
    No-op als de bron geen ``basic_auth`` met gebruikersnaam heeft.

    Parameters
    ----------
    source : SpatialSource
        Bron met ``authentication_type_id`` en ``authentication_config``.
    """
    cfg = getattr(source, "authentication_config", None) or {}
    if getattr(source, "authentication_type_id", None) == "basic_auth" and cfg.get("username"):
        userpwd = f"{cfg['username']}:{cfg.get('password', '')}"
        vorige = gdal.GetThreadLocalConfigOption("GDAL_HTTP_USERPWD")
        gdal.SetThreadLocalConfigOption("GDAL_HTTP_USERPWD", userpwd)
        try:
            yield
        finally:
            gdal.SetThreadLocalConfigOption("GDAL_HTTP_USERPWD", vorige)
    else:
        yield


def spatial_tiles_key(source_id: int) -> str:
    """Object-key van de PMTiles van een SpatialSource."""
    return f"spatial/{source_id}.pmtiles"


def gdal_input_for_source(source):
    """Bepaal de GDAL-input voor een bron.

    Returns
    -------
    tuple
        ``(contextmanager die het GDAL-pad yieldt, optionele laagnaam)``.
        Voor een bestand-bron is dat een lokale tempkopie van ``source.file``;
        voor een WFS-bron de GDAL WFS-connectiestring (geen tempbestand).

    Raises
    ------
    ValueError
        Als de bron geen bruikbare input heeft.
    """
    if source.source_type_id == WFS_SOURCE_TYPE:
        url = (source.source_config or {}).get("url")
        if not url:
            raise ValueError("WFS-bron heeft geen url in source_config.")
        typename = (source.source_config or {}).get("typename") or None
        return contextlib.nullcontext(f"WFS:{url}"), typename
    if source.source_type_id == "geojson":
        cfg = source.source_config or {}
        data = cfg.get("data") or cfg.get("url")
        if isinstance(data, str) and data.startswith(("http://", "https://")):
            # Remote GeoJSON-URL: laat GDAL het via /vsicurl streamen.
            return contextlib.nullcontext(f"/vsicurl/{data}"), None
    if not source.file:
        raise ValueError("Bron heeft geen bestand om tiles uit te genereren.")
    return _local_copy(source.file), None


def build_tiles_for_source(source_id: int) -> None:
    """Genereer PMTiles voor één SpatialSource en werk status + laagmetadata bij."""
    from rgs_django_spatial.models import SpatialLayer, SpatialSource

    obj = SpatialSource.objects.get(id=source_id)
    obj.tile_status = "bezig"
    obj.tile_fout = None
    obj.save(update_fields=["tile_status", "tile_fout"])

    try:
        gdal_ctx, layer_name = gdal_input_for_source(obj)
        # Zoombereik van de eerste gekoppelde laag, anders defaults.
        first_layer = SpatialLayer.objects.filter(source=obj).order_by("id").first()
        minzoom = (first_layer.min_zoom if first_layer and first_layer.min_zoom is not None else 0)
        maxzoom = (first_layer.max_zoom if first_layer and first_layer.max_zoom is not None else 14)

        with gdal_auth_config(obj), gdal_ctx as src:
            info = inspect_vector(src, layer_name)
            # Alle lagen + geometrieën in het bestand, voor de laag-beheer-UI.
            available_layers = inspect_layers(src)
            with tempfile.TemporaryDirectory() as td:
                dst = os.path.join(td, f"{source_id}.pmtiles")
                generate_pmtiles(src, dst, minzoom=minzoom, maxzoom=maxzoom,
                                 layers=[layer_name] if layer_name else None)
                store_pmtiles(spatial_tiles_key(source_id), dst)

        # Metadata naar alle gekoppelde lagen (source_layer = MVT-laagnaam).
        SpatialLayer.objects.filter(source=obj).update(
            source_layer=info.layer_name,
            geometry_type=info.geometry_type,
            extent=info.extent,
        )
        # Ook op de BRON bewaren: een laag die later (na het tilen) aan deze bron
        # gekoppeld wordt, mist anders source_layer en rendert niets. De frontend
        # valt terug op source_config.source_layer. available_layers toont in de
        # beheer-UI welke lagen + geometrieën beschikbaar zijn.
        cfg = dict(obj.source_config or {})
        cfg["source_layer"] = info.layer_name
        cfg["geometry_type"] = info.geometry_type
        cfg["available_layers"] = available_layers
        obj.source_config = cfg
        obj.tile_status = "klaar"
        obj.tile_fout = None
        obj.tiles_updated_at = timezone.now()
        obj.save(update_fields=["source_config", "tile_status", "tile_fout", "tiles_updated_at"])
        log.info("PMTiles gegenereerd voor SpatialSource %s (%s features)", source_id, info.feature_count)
    except Exception as e:  # noqa: BLE001 — fout in DB vastleggen, niet de thread laten crashen
        log.exception("PMTiles-generatie mislukt voor SpatialSource %s", source_id)
        obj.tile_status = "fout"
        obj.tile_fout = str(e)
        obj.save(update_fields=["tile_status", "tile_fout"])


def _thread_target(source_id: int) -> None:
    try:
        build_tiles_for_source(source_id)
    finally:
        connections.close_all()


def start_spatial_tile_build(source_id: int) -> None:
    """Start de tile-generatie in een daemon-thread (niet-blokkerend)."""
    threading.Thread(target=_thread_target, args=(source_id,), daemon=True).start()


def served_geojson_key(source_id: int) -> str:
    """Object-key van het geserveerde (naar WGS84 geherprojecteerde) GeoJSON."""
    return f"spatial/{source_id}.geojson"


def build_served_geojson_for_source(source_id: int, source_crs: str | None = None) -> None:
    """Herprojecteer het geüploade GeoJSON naar WGS84 en zet het klaar om te serveren.

    Synchroon (herprojectie van een precisie-gereduceerd GeoJSON is snel): zet
    ``source_config.data`` op de stabiele serveer-URL (``/api/spatial/{id}/geojson``,
    geen expiry — i.t.t. presigned PMTiles-URL's) en vult geometrietype + extent op
    de gekoppelde lagen. Gooit door bij een fout zodat de aanroeper 400 kan geven.

    Parameters
    ----------
    source_id : int
        PK van de SpatialSource (moet een geüpload ``file`` hebben).
    source_crs : str or None
        Overschrijf de bron-CRS (bv. ``"EPSG:28992"``); ``None`` = uit het bestand.
    """
    from rgs_django_spatial.models import SpatialLayer, SpatialSource

    from rgs_django_spatial.tiles.pmtiles import reproject_to_geojson
    from rgs_django_spatial.tiles.storage import store_pmtiles

    obj = SpatialSource.objects.get(id=source_id)
    if not obj.file:
        raise ValueError("Bron heeft geen bestand om te herprojecteren.")

    with _local_copy(obj.file) as src:
        with tempfile.TemporaryDirectory() as td:
            dst = os.path.join(td, f"{source_id}.geojson")
            reproject_to_geojson(src, dst, source_crs=source_crs)
            # Inspecteer het RESULTAAT (WGS84), zodat extent/geometrie kloppen
            # ongeacht de bron-CRS.
            info = inspect_vector(dst)
            store_pmtiles(served_geojson_key(source_id), dst)

    cfg = dict(obj.source_config or {})
    cfg["data"] = f"/api/spatial/{source_id}/geojson"
    obj.source_config = cfg
    obj.save(update_fields=["source_config"])

    SpatialLayer.objects.filter(source=obj).update(
        geometry_type=info.geometry_type,
        extent=info.extent,
    )
    log.info("GeoJSON geserveerd voor SpatialSource %s (%s features)", source_id, info.feature_count)
