"""REST-endpoints voor SpatialSource-ingest (upload, tile-generatie, tile-URL's)."""
import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Schema
from ninja.files import UploadedFile

from rgs_django_spatial.tiles.ogc_capabilities import discover_layers
from rgs_django_spatial.tiles.spatial_service import (
    build_served_geojson_for_source,
    gdal_auth_config,
    gdal_input_for_source,
    served_geojson_key,
    spatial_tiles_key,
    start_spatial_tile_build,
)
from rgs_django_spatial.tiles.storage import pmtiles_url, read_object

log = logging.getLogger(__name__)

router = Router(tags=["spatial"])


class SpatialTileUrlSchema(Schema):
    source_id: int
    tiles_url: str
    tiles_key: str


class ErrorResponse(Schema):
    error: str


@router.get("/lagen/", response=list[SpatialTileUrlSchema])
def list_tile_urls(request: HttpRequest):
    """Actuele (presigned) PMTiles-URL's van alle bronnen met klare tiles."""
    from rgs_django_spatial.models import SpatialSource

    out = []
    for obj in SpatialSource.objects.filter(tile_status="klaar"):
        out.append({
            "source_id": obj.id,
            "tiles_url": pmtiles_url(spatial_tiles_key(obj.id)),
            "tiles_key": spatial_tiles_key(obj.id),
        })
    return out


class CapabilitiesRequest(Schema):
    service: str
    url: str
    username: Optional[str] = None
    password: Optional[str] = None


class CapabilityLayerSchema(Schema):
    name: str
    title: str
    abstract: Optional[str] = None
    bbox_wgs84: Optional[list[float]] = None
    crs: list[str] = []
    formats: list[str] = []
    queryable: Optional[bool] = None
    geometry_type: Optional[str] = None


class CapabilitiesSchema(Schema):
    service: str
    version: Optional[str] = None
    title: Optional[str] = None
    layers: list[CapabilityLayerSchema]


@router.post("/capabilities/", response={200: CapabilitiesSchema, 400: ErrorResponse})
def capabilities(request: HttpRequest, payload: CapabilitiesRequest):
    """Haal via GetCapabilities de beschikbare lagen van een WMS/WFS-server op.

    Server-side (browser mag externe hosts niet ophalen). Alleen ``http``/``https``
    is toegestaan als kleine SSRF-mitigatie; alle fouten worden vertaald naar een
    nette NL-melding met HTTP 400.
    """
    service = (payload.service or "").lower()
    if service not in ("wms", "wfs"):
        return 400, {"error": "Kies WMS of WFS."}
    if not payload.url.lower().startswith(("http://", "https://")):
        return 400, {"error": "Alleen http- of https-URL's zijn toegestaan."}
    try:
        result = discover_layers(
            service, payload.url,
            username=(payload.username or None),
            password=(payload.password or None),
        )
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:  # noqa: BLE001 — externe fout netjes terug naar de gebruiker
        log.warning("GetCapabilities mislukt voor %s: %s", payload.url, e)
        msg = str(e).lower()
        if "401" in msg or "403" in msg or "auth" in msg:
            return 400, {"error": "Authenticatie mislukt of geen toegang."}
        if "timed out" in msg or "timeout" in msg:
            return 400, {"error": "Server niet bereikbaar of te traag."}
        return 400, {"error": "Geen geldig WMS/WFS-antwoord op deze URL."}
    return 200, result


class VeldWaardenSchema(Schema):
    waarden: list
    afgekapt: bool


@router.get("/{id}/veld-waarden/", response={200: VeldWaardenSchema, 400: ErrorResponse, 404: ErrorResponse})
def veld_waarden(request: HttpRequest, id: int, veld: str, laag: Optional[str] = None):
    """Distinct waarden van een attribuutveld uit de bron (max 20), voor de
    categorie-auto-load in de stijleditor. Werkt voor bestand-, WFS- en
    remote-geojson-bronnen; remote bronnen worden gecapt op de eerste 500 features."""
    from rgs_django_spatial.models import SpatialSource

    from rgs_django_spatial.tiles.pmtiles import distinct_veldwaarden

    obj = get_object_or_404(SpatialSource, id=id)
    try:
        gdal_ctx, layer_name = gdal_input_for_source(obj)
    except ValueError as e:
        return 400, {"error": str(e)}
    # Remote bronnen (geen lokaal bestand): scan-cap zodat een trage server niet blokkeert.
    max_features = None if obj.file else 500
    laag_keuze = laag or layer_name
    try:
        with gdal_auth_config(obj), gdal_ctx as src:
            waarden, afgekapt = distinct_veldwaarden(src, veld, laag_keuze, max_features=max_features)
    except (ValueError, RuntimeError) as e:
        return 400, {"error": str(e)}
    return 200, {"waarden": waarden, "afgekapt": afgekapt}


class VeldenSchema(Schema):
    velden: list[str]


@router.get("/{id}/velden/", response={200: VeldenSchema, 400: ErrorResponse, 404: ErrorResponse})
def velden(request: HttpRequest, id: int, laag: Optional[str] = None):
    """Attribuut-veldnamen van een bron, voor de veld-dropdown in de stijleditor.

    Leest de bron live in met GDAL (in plaats van te vertrouwen op
    ``available_layers.fields``), zodat de dropdown ook werkt voor bronnen die
    getild zijn vóórdat die kolom bestond. Werkt voor bestand-, WFS- en
    remote-geojson-bronnen.
    """
    from rgs_django_spatial.models import SpatialSource

    from rgs_django_spatial.tiles.pmtiles import inspect_layers

    obj = get_object_or_404(SpatialSource, id=id)
    try:
        gdal_ctx, layer_name = gdal_input_for_source(obj)
    except ValueError as e:
        return 400, {"error": str(e)}
    try:
        with gdal_auth_config(obj), gdal_ctx as src:
            lagen = inspect_layers(src)
    except (ValueError, RuntimeError) as e:
        return 400, {"error": str(e)}
    keuze = laag or layer_name
    gekozen = next((l for l in lagen if l["name"] == keuze), lagen[0] if lagen else None)
    return 200, {"velden": gekozen["fields"] if gekozen else []}


@router.post("/{id}/upload/", response={202: None, 404: ErrorResponse, 400: ErrorResponse})
def upload_bestand(request: HttpRequest, id: int, bestand: File[UploadedFile]):
    """Sla een .gpkg/.geojson op bij de bron en start tile-generatie."""
    from rgs_django_spatial.models import SpatialSource

    obj = get_object_or_404(SpatialSource, id=id)
    naam = (bestand.name or "").lower()
    if not naam.endswith((".gpkg", ".geojson", ".json")):
        return 400, {"error": "Alleen .gpkg, .geojson of .json wordt ondersteund."}
    if obj.file:
        obj.file.delete(save=False)
    obj.file.save(bestand.name, bestand, save=True)
    start_spatial_tile_build(obj.id)
    return 202, None


@router.post("/{id}/genereer-tiles/", response={202: None, 404: ErrorResponse, 400: ErrorResponse})
def genereer_tiles(request: HttpRequest, id: int):
    from rgs_django_spatial.models import SpatialSource

    obj = get_object_or_404(SpatialSource, id=id)
    try:
        gdal_input_for_source(obj)  # valideert dat er input is (bestand of WFS-url)
    except ValueError as e:
        return 400, {"error": str(e)}
    start_spatial_tile_build(obj.id)
    return 202, None


@router.post("/{id}/upload-geojson/", response={200: None, 404: ErrorResponse, 400: ErrorResponse})
def upload_served_geojson(
    request: HttpRequest,
    id: int,
    bestand: File[UploadedFile],
    source_crs: Form[Optional[str]] = None,
):
    """Upload een GeoJSON, herprojecteer naar WGS84 en zet klaar om direct te serveren.

    Anders dan /upload/ (die PMTiles bouwt) wordt dit bestand niet getiled maar
    als GeoJSON aangeboden via /{id}/geojson. ``source_crs`` overschrijft de
    bron-CRS (bv. ``EPSG:28992``); leeg = uit het bestand lezen.
    """
    from rgs_django_spatial.models import SpatialSource

    obj = get_object_or_404(SpatialSource, id=id)
    naam = (bestand.name or "").lower()
    if not naam.endswith((".geojson", ".json")):
        return 400, {"error": "Alleen .geojson of .json wordt ondersteund."}
    if obj.file:
        obj.file.delete(save=False)
    obj.file.save(bestand.name, bestand, save=True)
    try:
        build_served_geojson_for_source(obj.id, source_crs=(source_crs or None))
    except Exception as e:  # noqa: BLE001 — fout terug naar de gebruiker
        log.exception("GeoJSON-herprojectie mislukt voor SpatialSource %s", obj.id)
        return 400, {"error": f"Herprojectie mislukt: {e}"}
    return 200, None


@router.get("/{id}/geojson/", response={200: None, 404: ErrorResponse})
def served_geojson(request: HttpRequest, id: int):
    """Serveer het (naar WGS84 geherprojecteerde) GeoJSON van een bestand-bron.

    De frontend zet ``source_config.data = /api/spatial/{id}/geojson`` (zonder
    trailing slash); de Next-proxy voegt de slash toe die deze route vereist.
    """
    try:
        data = read_object(served_geojson_key(id))
    except FileNotFoundError:
        return 404, {"error": "Geen GeoJSON voor deze bron."}
    return HttpResponse(data, content_type="application/geo+json")


@router.get("/mapproxy-config.yaml", response={200: None})
def mapproxy_config(request: HttpRequest):
    """Gegenereerde MapProxy-config; wordt cluster-intern gepolld door de
    config-sync-sidecar in de MapProxy-pod (niet via de ingress ontsloten)."""
    from rgs_django_spatial.mapproxy import heeft_reproject_bronnen, render_mapproxy_yaml

    # Lege config laat MapProxy crashen (IndexError op layers: []); 404 laat de
    # config-sync-sidecar (curl -f) netjes falen zodat er geen kapot bestand komt.
    if not heeft_reproject_bronnen():
        return HttpResponse(status=404)
    return HttpResponse(render_mapproxy_yaml(), content_type="text/yaml; charset=utf-8")
