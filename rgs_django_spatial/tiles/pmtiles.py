"""GDAL-gebaseerde, Django-onafhankelijke helpers om vectorbronnen
(GeoPackage/GeoJSON/WFS) te inspecteren en naar PMTiles om te zetten. Pure
functies zodat ze los testbaar zijn.
"""
import os
import uuid
from dataclasses import dataclass

from osgeo import gdal, ogr, osr

gdal.UseExceptions()


@dataclass
class GpkgInfo:
    """Samenvatting van de eerste laag in een GeoPackage.

    Attributes
    ----------
    layer_name : str
        Naam van de (eerste) laag in het GeoPackage; tevens de MVT source-layer.
    geometry_type : str
        Vereenvoudigd geometrietype: 'point', 'line' of 'polygon'.
    feature_count : int
        Aantal features in de laag.
    extent : list of float
        Bounding box [minx, miny, maxx, maxy] in EPSG:4326.
    """
    layer_name: str
    geometry_type: str
    feature_count: int
    extent: list[float]


def _simple_geom(ogr_geom_name: str) -> str:
    """Vertaal een OGR-geometrienaam naar 'point', 'line' of 'polygon'."""
    name = (ogr_geom_name or "").lower()
    if "point" in name:
        return "point"
    if "line" in name:
        return "line"
    if "polygon" in name or "surface" in name:
        return "polygon"
    return "polygon"


def inspect_layers(path: str) -> list[dict]:
    """Geef per laag in een vectorbron de naam, het geometrietype en aantal features.

    Bedoeld om in de beheer-UI te tonen welke lagen + geometrieën een geüpload
    bestand bevat — een GeoPackage kan meerdere lagen hebben.

    Parameters
    ----------
    path : str
        Pad naar het vectorbestand (bv. ``.gpkg`` of ``.geojson``).

    Returns
    -------
    list of dict
        Per laag ``{"name": str, "geometry_type": str, "feature_count": int, "fields": [str, ...]}``.
    """
    ds = gdal.OpenEx(path, gdal.OF_VECTOR)
    if ds is None:
        raise ValueError("Bron kon niet als vectorbestand geopend worden.")
    try:
        out = []
        for i in range(ds.GetLayerCount()):
            layer = ds.GetLayer(i)
            defn = layer.GetLayerDefn()
            fields = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]
            out.append({
                "name": layer.GetName(),
                "geometry_type": _simple_geom(ogr.GeometryTypeToName(layer.GetGeomType())),
                "feature_count": int(layer.GetFeatureCount()),
                "fields": fields,
            })
        return out
    finally:
        # GDAL-dataset altijd vrijgeven.
        ds = None


def inspect_vector(path: str, layer_name: str | None = None) -> GpkgInfo:
    """Lees één vectorlaag uit (eerste laag, of ``layer_name``) en geef metadata terug.

    Parameters
    ----------
    path : str
        Pad of GDAL-connectiestring naar de vectorbron (bv. ``.gpkg``, ``.geojson``
        of ``WFS:...``).
    layer_name : str or None, optional
        Naam van de te lezen laag. Als ``None``, wordt de eerste laag gebruikt.

    Returns
    -------
    GpkgInfo
        Laaginfo met naam, geometrietype, aantal features en WGS84-extent.

    Raises
    ------
    ValueError
        Als de bron geen leesbare vectorlaag bevat, of ``layer_name`` niet
        gevonden wordt.
    """
    ds = gdal.OpenEx(path, gdal.OF_VECTOR)
    if ds is None or ds.GetLayerCount() == 0:
        raise ValueError("Bron bevat geen leesbare vectorlaag.")
    try:
        layer = ds.GetLayerByName(layer_name) if layer_name else ds.GetLayer(0)
        if layer is None:
            raise ValueError(f"Laag '{layer_name}' niet gevonden in de bron.")
        name = layer.GetName()
        geom = _simple_geom(ogr.GeometryTypeToName(layer.GetGeomType()))
        count = int(layer.GetFeatureCount())

        minx, maxx, miny, maxy = layer.GetExtent()
        extent = [minx, miny, maxx, maxy]
        src_srs = layer.GetSpatialRef()
        if src_srs is not None:
            tgt = osr.SpatialReference()
            tgt.ImportFromEPSG(4326)
            tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            src = src_srs.Clone()
            src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            ct = osr.CoordinateTransformation(src, tgt)
            x0, y0, _ = ct.TransformPoint(minx, miny)
            x1, y1, _ = ct.TransformPoint(maxx, maxy)
            extent = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
    finally:
        # GDAL-dataset altijd vrijgeven, ook bij een exception.
        ds = None
    return GpkgInfo(layer_name=name, geometry_type=geom, feature_count=count, extent=extent)


def distinct_veldwaarden(path: str, veld: str, laag: str | None = None,
                         limiet: int = 20, max_features: int | None = None) -> tuple[list, bool]:
    """Geef tot ``limiet`` unieke waarden van een attribuutveld uit een vectorlaag.

    Parameters
    ----------
    path : str
        Pad naar het vectorbestand (bv. ``.gpkg`` of ``.geojson``).
    veld : str
        Naam van het attribuutveld.
    laag : str or None, optional
        Naam van de laag; ``None`` = eerste laag.
    limiet : int
        Maximaal aantal terug te geven waarden.
    max_features : int or None, optional
        Begrens het aantal gescande features (voor trage remote WFS/URL-bronnen);
        ``None`` = alle features scannen.

    Returns
    -------
    tuple
        ``(waarden, afgekapt)`` — de eerste ``limiet`` unieke niet-lege waarden en
        of er meer dan ``limiet`` unieke waarden waren.

    Raises
    ------
    ValueError
        Als de bron niet leesbaar is, de laag niet bestaat of het veld ontbreekt.
    """
    try:
        ds = gdal.OpenEx(path, gdal.OF_VECTOR)
    except RuntimeError as e:
        raise ValueError(str(e)) from e
    if ds is None:
        raise ValueError("Bron kon niet als vectorbestand geopend worden.")
    try:
        layer = ds.GetLayerByName(laag) if laag else ds.GetLayer(0)
        if layer is None:
            raise ValueError(f"Laag '{laag}' niet gevonden in de bron.")
        if layer.GetLayerDefn().GetFieldIndex(veld) < 0:
            raise ValueError(f"Veld '{veld}' niet gevonden in de laag.")
        gezien: list = []
        seen: set = set()
        gescand = 0
        layer.ResetReading()
        for feat in layer:
            gescand += 1
            w = feat.GetField(veld)
            if w is not None and w != "" and w not in seen:
                seen.add(w)
                gezien.append(w)
                if len(gezien) > limiet:
                    break
            if max_features is not None and gescand >= max_features:
                break
        afgekapt = len(gezien) > limiet
        return gezien[:limiet], afgekapt
    finally:
        # GDAL-dataset altijd vrijgeven.
        ds = None


def generate_pmtiles(src_path: str, dst_path: str, minzoom: int = 0, maxzoom: int = 14,
                      layers: list[str] | None = None) -> None:
    """Genereer een PMTiles-bestand uit een vectorbron met GDAL.

    De PMTiles-driver herprojecteert automatisch vanuit de bron-CRS naar
    web-mercator. Een bestaand doelbestand wordt overschreven.

    Parameters
    ----------
    src_path : str
        Pad of GDAL-connectiestring naar de vectorbron (bv. ``.gpkg``, ``.geojson``
        of ``WFS:...``).
    dst_path : str
        Pad naar het te schrijven ``.pmtiles``-bestand.
    minzoom, maxzoom : int
        Zoombereik van de tile-pyramide.
    layers : list of str or None, optional
        Te vertalen laagnamen. Als ``None``, vertaalt GDAL alle lagen van de bron.
    """
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    # Schrijf naar een uniek tijdelijk bestand en vervang het doel pas atomair na
    # succes. Zo blijft een lopende lezer altijd een compleet bestand zien, raakt
    # er bij gelijktijdige (her)generatie of een crash geen half bestand op de
    # serveerlocatie, en is er geen torn-write op dezelfde pad.
    tmp_path = f"{dst_path}.{uuid.uuid4().hex}.tmp"
    try:
        gdal.VectorTranslate(
            tmp_path,
            src_path,
            format="PMTiles",
            layers=layers,
            datasetCreationOptions=[f"MINZOOM={minzoom}", f"MAXZOOM={maxzoom}"],
        )
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("PMTiles-bestand is niet (correct) aangemaakt.")
        os.replace(tmp_path, dst_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def reproject_to_geojson(
    src_path: str,
    dst_path: str,
    source_crs: str | None = None,
    precision: int = 6,
) -> None:
    """Herprojecteer een vectorbestand naar WGS84-GeoJSON met beperkte precisie.

    MapLibre interpreteert een GeoJSON-bron altijd als EPSG:4326, dus een bestand
    in bv. EPSG:28992 wordt hier naar WGS84 omgezet. De coördinaat-precisie wordt
    beperkt (aantal decimalen) om de bestandsgrootte te drukken.

    Parameters
    ----------
    src_path : str
        Pad naar het bron-vectorbestand (GeoJSON/GeoPackage/…).
    dst_path : str
        Pad naar het te schrijven ``.geojson``-bestand (WGS84).
    source_crs : str or None
        Overschrijf de bron-CRS (bv. ``"EPSG:28992"``). ``None`` = uit het bestand
        lezen (of WGS84 als het bestand geen CRS declareert).
    precision : int
        Aantal decimalen in de uitvoer (6 ≈ ~0,1 m). Bepaalt de bestandsgrootte.
    """
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    # Atomair schrijven: temp + os.replace, zoals bij generate_pmtiles.
    tmp_path = f"{dst_path}.{uuid.uuid4().hex}.tmp"
    try:
        kwargs = {
            "format": "GeoJSON",
            "dstSRS": "EPSG:4326",
            "layerCreationOptions": [f"COORDINATE_PRECISION={precision}"],
        }
        if source_crs:
            kwargs["srcSRS"] = source_crs
        gdal.VectorTranslate(tmp_path, src_path, **kwargs)
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("GeoJSON-herprojectie leverde geen bestand op.")
        os.replace(tmp_path, dst_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
