"""Genereert de MapProxy-configuratie (een MultiMapProxy-configuratiebestand)
uit SpatialSource-records met ``reproject=True``.

Per bron beschrijft ``source_config.upstream`` de bovenliggende dienst:
``{"type": "wms"|"arcgis", "url", "layers", "srs": [..], "layer_name"}``.
De gegenereerde laag is bereikbaar als
``/mapproxy/{app}/wmts/{layer_name}/webmercator/{z}/{x}/{y}.png``.

De consumer-app bepaalt de MultiMapProxy-bestandsnaam (het ``{app}``-segment in
het pad); dit pakket genereert alleen de YAML-inhoud. De WMS-servicetitel komt
uit ``settings.MAPPROXY_TITLE`` (default ``"MapProxy"``).
"""
import logging

import yaml
from django.conf import settings

log = logging.getLogger(__name__)


def render_mapproxy_yaml() -> str:
    from rgs_django_spatial.models import SpatialSource

    layers, caches, sources = [], {}, {}
    for src in SpatialSource.objects.filter(reproject=True).order_by("id"):
        up = (src.source_config or {}).get("upstream") or {}
        name = up.get("layer_name")
        if not name or not up.get("url") or up.get("type") not in ("wms", "arcgis"):
            log.warning("MapProxy: bron %s (%s) overgeslagen — onvolledige upstream-config", src.id, src.name)
            continue
        layers.append({"name": name, "title": src.name, "sources": [f"{name}_cache"]})
        caches[f"{name}_cache"] = {
            "grids": ["webmercator"],
            "sources": [f"{name}_source"],
            "cache": {"type": "file"},
        }
        req = {"url": up["url"], "layers": str(up.get("layers", "0"))}
        sources[f"{name}_source"] = {
            "type": up["type"],
            "req": req,
            "supported_srs": up.get("srs") or ["EPSG:28992", "EPSG:4326"],
            "seed_only": False,
        }

    cfg = {
        "services": {
            "wms": {"md": {"title": getattr(settings, "MAPPROXY_TITLE", "MapProxy")}},
            "tms": {"use_grid_names": True},
            "wmts": None,
        },
        "layers": layers,
        "caches": caches,
        "sources": sources,
        "grids": {"webmercator": {"base": "GLOBAL_WEBMERCATOR", "srs": "EPSG:3857", "origin": "nw"}},
        "globals": {
            "cache": {"base_dir": "/mapproxy/cache_data"},
            "image": {"resampling_method": "bilinear", "formats": {"png": {"transparent": True}}},
        },
    }
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)


def heeft_reproject_bronnen() -> bool:
    """True als er minstens één bron met een bruikbare upstream-config is."""
    from rgs_django_spatial.models import SpatialSource

    for src in SpatialSource.objects.filter(reproject=True):
        up = (src.source_config or {}).get("upstream") or {}
        if up.get("layer_name") and up.get("url") and up.get("type") in ("wms", "arcgis"):
            return True
    return False
