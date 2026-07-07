"""Where a laag's ``.pmtiles`` lives and how the browser addresses it.

Gated on ``settings.TILES_STORAGE``:

* ``"local"`` (default) — the file lives under ``VAR_DIR/tiles/`` and is served
  by the in-cluster ``tiles-nginx`` sidecar at ``/tiles/{id}.pmtiles``.
* ``"s3"`` — the file is uploaded to a **private** Scaleway Object Storage
  bucket; the browser gets a short-lived **presigned GET URL** so the bucket
  never needs to be public. PMTiles' HTTP range requests hit S3 directly.

S3 connection settings are read from ``settings.TILES_S3`` (a dict assembled in
settings.py, only when TILES_STORAGE == "s3").

Vereiste consumer-settings
--------------------------
TILES_STORAGE ("local"|"s3", default "local"), VAR_DIR (default "var"),
TILES_URL_TTL (default 86400) en — alleen bij "s3" — TILES_S3
(dict: key, secret, endpoint_url, bucket, optioneel prefix/region).
"""
import os
import shutil

from django.conf import settings

LOCAL_BACKEND = "local"
S3_BACKEND = "s3"


def tiles_backend() -> str:
    return getattr(settings, "TILES_STORAGE", LOCAL_BACKEND) or LOCAL_BACKEND


def _tiles_key(key: str, prefix: str = "") -> str:
    """Volledige object-key incl. optionele bucket-prefix."""
    prefix = (prefix or "").strip("/")
    key = key.lstrip("/")
    return f"{prefix}/{key}" if prefix else key


def local_pmtiles_path(key: str) -> str:
    return os.path.join(getattr(settings, "VAR_DIR", "var"), "tiles", *key.split("/"))


def _s3fs():
    """Build an s3fs filesystem from settings.TILES_S3."""
    import s3fs

    cfg = getattr(settings, "TILES_S3", {})
    return s3fs.S3FileSystem(
        key=cfg["key"],
        secret=cfg["secret"],
        endpoint_url=cfg["endpoint_url"],
        client_kwargs={"region_name": cfg.get("region", "nl-ams")},
    )


def _s3_object_path(key: str) -> str:
    cfg = getattr(settings, "TILES_S3", {})
    return f"{cfg['bucket']}/{_tiles_key(key, cfg.get('prefix', ''))}"


def store_pmtiles(key: str, local_path: str) -> None:
    """Persist a freshly generated ``.pmtiles`` (from ``local_path``) to the backend."""
    if tiles_backend() == S3_BACKEND:
        fs = _s3fs()
        fs.put_file(local_path, _s3_object_path(key))
        os.remove(local_path)
        return
    dst = local_pmtiles_path(key)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(local_path, dst)


def delete_pmtiles(key: str) -> None:
    """Remove a dataset's PMTiles from the active backend (idempotent)."""
    if tiles_backend() == S3_BACKEND:
        fs = _s3fs()
        path = _s3_object_path(key)
        if fs.exists(path):
            fs.rm(path)
        return
    local = local_pmtiles_path(key)
    if os.path.exists(local):
        os.remove(local)


def pmtiles_url(key: str) -> str:
    """URL the frontend loads the PMTiles from (stable path, or presigned S3 URL)."""
    if tiles_backend() == S3_BACKEND:
        ttl = int(getattr(settings, "TILES_URL_TTL", 86400))
        return _s3fs().sign(_s3_object_path(key), expiration=ttl)
    return f"/tiles/{key}"


def read_object(key: str) -> bytes:
    """Lees een opgeslagen object (bv. een geserveerd ``.geojson``) uit de backend.

    Storage-agnostisch: leest uit S3 (via s3fs) of van het lokale pad. Bedoeld voor
    kleine bestanden die door Django worden gestreamd (i.t.t. PMTiles, die de
    browser via een presigned URL rechtstreeks bij S3 ophaalt).

    Raises
    ------
    FileNotFoundError
        Als het object niet bestaat.
    """
    if tiles_backend() == S3_BACKEND:
        fs = _s3fs()
        path = _s3_object_path(key)
        if not fs.exists(path):
            raise FileNotFoundError(key)
        with fs.open(path, "rb") as f:
            return f.read()
    with open(local_pmtiles_path(key), "rb") as f:
        return f.read()
