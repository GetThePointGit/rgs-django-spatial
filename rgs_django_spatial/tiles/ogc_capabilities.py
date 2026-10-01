"""OWSLib-gebaseerde ontdekking van WMS/WFS-lagen via GetCapabilities.

Splitst pure parsing (``parse_wms``/``parse_wfs``, los testbaar met stubs) van
de netwerk-ophaal (``discover_layers``). De parsers lezen alleen attributen die
OWSLib op zijn ``contents``-items zet.
"""

from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService


def _bbox(obj):
    """Geef de WGS84-bbox van een OWSLib-content-item als ``[minx,miny,maxx,maxy]`` of ``None``."""
    bb = getattr(obj, "boundingBoxWGS84", None)
    if not bb:
        return None
    return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]


def parse_wms(wms) -> list[dict]:
    """Map de named layers van een OWSLib ``WebMapService`` naar wizard-dicts.

    Parameters
    ----------
    wms : owslib.wms.WebMapService or stub
        Object met ``.contents`` (dict van laagnaam→laagobject) en
        ``.getOperationByName("GetMap").formatOptions``.

    Returns
    -------
    list of dict
        Per laag ``{"name","title","abstract","bbox_wgs84","crs","formats","queryable","geometry_type"}``.
        Groep-lagen zonder naam (lege sleutel) worden overgeslagen.
    """
    try:
        formats = list(wms.getOperationByName("GetMap").formatOptions or [])
    except Exception:  # noqa: BLE001 — formats zijn optioneel
        formats = []
    out = []
    for name, layer in wms.contents.items():
        if not name:
            continue
        out.append(
            {
                "name": name,
                "title": getattr(layer, "title", None) or name,
                "abstract": getattr(layer, "abstract", None),
                "bbox_wgs84": _bbox(layer),
                "crs": list(getattr(layer, "crsOptions", []) or []),
                "formats": formats,
                "queryable": bool(getattr(layer, "queryable", 0)),
                "geometry_type": None,
            }
        )
    return out


def parse_wfs(wfs) -> list[dict]:
    """Map de feature types van een OWSLib ``WebFeatureService`` naar wizard-dicts.

    Parameters
    ----------
    wfs : owslib.wfs.WebFeatureService or stub
        Object met ``.contents`` (dict van typename→feature-type-object).

    Returns
    -------
    list of dict
        Per feature type ``{"name","title","abstract","bbox_wgs84","crs","formats","queryable","geometry_type"}``.
    """
    out = []
    for name, ft in wfs.contents.items():
        out.append(
            {
                "name": name,
                "title": getattr(ft, "title", None) or name,
                "abstract": getattr(ft, "abstract", None),
                "bbox_wgs84": _bbox(ft),
                "crs": [str(c) for c in (getattr(ft, "crsOptions", []) or [])],
                "formats": [],
                "queryable": None,
                "geometry_type": None,
            }
        )
    return out


def discover_layers(
    service: str, url: str, username: str | None = None, password: str | None = None, timeout: int = 15
) -> dict:
    """Haal live GetCapabilities op en geef de gemapte lagenlijst terug.

    Parameters
    ----------
    service : str
        ``"wms"`` of ``"wfs"``.
    url : str
        Basis-URL van de service.
    username, password : str or None
        Optionele basic-auth-credentials.
    timeout : int
        Netwerk-timeout in seconden.

    Returns
    -------
    dict
        ``{"service","version","title","layers":[...]}``.

    Raises
    ------
    ValueError
        Bij een onbekende ``service``.
    """
    if service == "wms":
        svc = WebMapService(url, username=username, password=password, timeout=timeout)
        layers = parse_wms(svc)
    elif service == "wfs":
        svc = WebFeatureService(url, username=username, password=password, timeout=timeout)
        layers = parse_wfs(svc)
    else:
        raise ValueError(f"Onbekende service: {service}")
    return {
        "service": service,
        "version": getattr(svc, "version", None),
        "title": getattr(getattr(svc, "identification", None), "title", None),
        "layers": layers,
    }
