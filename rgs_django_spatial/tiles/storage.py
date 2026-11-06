"""Opslag van de PMTiles (en geserveerde GeoJSON) van een bron via een Django-storage.

De tiles staan in een gewone Django-storage uit ``settings.STORAGES``, standaard
onder de alias ``"tiles"`` (instelbaar met ``SPATIAL_TILES_STORAGE_ALIAS``).
Deze module kent geen S3-details: lokaal of object storage is een kwestie van
één ``STORAGES``-regel in het project, net als voor media.

Eisen aan de storage
--------------------
* ``save(key, content)`` moet ``key`` ongewijzigd teruggeven: zet de storage
  op overschrijven (``FileSystemStorage``: ``allow_overwrite=True``;
  ``django_fsspec.FsspecStorage``: ``on_collision="overwrite"``). Een storage die
  hernoemt geeft een ``ImproperlyConfigured``.
* ``url(key)`` geeft het pad waar de browser de tiles laadt; voor een lokale
  storage is dat ``base_url="/tiles/"`` (bediend door bv. een nginx-sidecar).
* Optioneel ``url_signed(key, expires=...)`` (``FsspecStorage`` op S3): dan krijgt
  de browser een kortlevende presigned GET-URL en hoeft de bucket niet publiek.
  Gooit de storage daarbij ``NotImplementedError`` (geen S3-backend), dan valt
  :func:`pmtiles_url` terug op ``url()``.

Voorbeeld (lokaal)::

    STORAGES["tiles"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": VAR_DIR / "tiles", "base_url": "/tiles/", "allow_overwrite": True},
    }

Voorbeeld (S3, private bucket, presigned URL's)::

    STORAGES["tiles"] = {
        "BACKEND": "django_fsspec.FsspecStorage",
        "OPTIONS": {
            "on_collision": "overwrite",
            "storage_config": {
                "protocol": "s3",
                "key": S3_ACCESS_KEY, "secret": S3_SECRET_KEY,
                "endpoint_url": "https://s3.nl-ams.scw.cloud",
                "client_kwargs": {"region_name": "nl-ams"},
                "relative_to_path": "mijn-bucket/prefix",
            },
        },
    }

Overgangsregeling (één release): ontbreekt de alias maar staan de oude settings
``TILES_STORAGE``/``TILES_S3``/``VAR_DIR`` er nog, dan bouwt deze module daar
intern een gelijkwaardige ``FsspecStorage`` van (django-fsspec vereist) en
geeft een ``DeprecationWarning``. ``TILES_URL_TTL`` (seconden, default 86400)
blijft de geldigheid van presigned URL's bepalen.
"""

import os
import warnings

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.core.files.storage import InvalidStorageError, storages

DEFAULT_STORAGE_ALIAS = "tiles"
DEFAULT_URL_TTL = 86400

_LEGACY_SETTINGS = ("TILES_STORAGE", "TILES_S3")


def tiles_storage():
    """Geef de Django-storage waarin de tiles staan.

    Returns
    -------
    django.core.files.storage.Storage
        ``storages[alias]`` met ``alias`` uit ``SPATIAL_TILES_STORAGE_ALIAS``
        (default ``"tiles"``), of de overgangs-storage uit de oude settings.

    Raises
    ------
    ImproperlyConfigured
        Als de alias ontbreekt en er ook geen oude ``TILES_*``-settings zijn.
    """
    alias = getattr(settings, "SPATIAL_TILES_STORAGE_ALIAS", DEFAULT_STORAGE_ALIAS)
    try:
        return storages[alias]
    except InvalidStorageError:
        legacy = _legacy_storage()
        if legacy is not None:
            return legacy
        raise ImproperlyConfigured(
            f"rgs_django_spatial: geen storage met alias {alias!r} in settings.STORAGES. "
            "Voeg een 'tiles'-storage toe (zie rgs_django_spatial.tiles.storage) of zet "
            "SPATIAL_TILES_STORAGE_ALIAS op een bestaande alias."
        ) from None


def _legacy_storage():
    """Bouw een storage uit de oude ``TILES_STORAGE``/``TILES_S3``-settings, of ``None``.

    Verdwijnt na deze overgangsrelease; zie de module-docstring.
    """
    if not any(hasattr(settings, naam) for naam in _LEGACY_SETTINGS):
        return None
    try:
        from django_fsspec import FsspecStorage
    except ImportError as exc:  # pragma: no cover - afhankelijk van de omgeving
        raise ImproperlyConfigured(
            "rgs_django_spatial: de oude TILES_STORAGE/TILES_S3-settings vereisen django-fsspec. "
            "Installeer django-fsspec of configureer STORAGES['tiles']."
        ) from exc

    warnings.warn(
        "rgs_django_spatial: TILES_STORAGE/TILES_S3/VAR_DIR zijn vervangen door "
        "settings.STORAGES['tiles'] en verdwijnen in de volgende release.",
        DeprecationWarning,
        stacklevel=3,
    )
    backend = getattr(settings, "TILES_STORAGE", None) or "local"
    if backend == "s3":
        cfg = dict(getattr(settings, "TILES_S3", None) or {})
        root = cfg["bucket"]
        prefix = (cfg.get("prefix") or "").strip("/")
        if prefix:
            root = f"{root}/{prefix}"
        return FsspecStorage(
            on_collision="overwrite",
            storage_config={
                "protocol": "s3",
                "key": cfg.get("key"),
                "secret": cfg.get("secret"),
                "endpoint_url": cfg.get("endpoint_url"),
                "client_kwargs": {"region_name": cfg.get("region", "nl-ams")},
                "relative_to_path": root,
            },
        )
    root = os.path.abspath(os.path.join(getattr(settings, "VAR_DIR", None) or "var", "tiles"))
    return FsspecStorage(
        base_url="/tiles/",
        on_collision="overwrite",
        storage_config={"protocol": "file", "auto_mkdir": True, "relative_to_path": root},
    )


def store_pmtiles(key: str, local_path: str) -> None:
    """Sla een vers gegenereerd bestand (``local_path``) op onder ``key`` en ruim het lokale op.

    Parameters
    ----------
    key : str
        Objectnaam binnen de tiles-storage, bv. ``"spatial/7.pmtiles"``.
    local_path : str
        Pad van het zojuist gebouwde bestand; wordt na opslaan verwijderd.

    Raises
    ------
    ImproperlyConfigured
        Als de storage het bestand onder een andere naam opslaat (niet op
        overschrijven ingesteld); het verkeerd opgeslagen object wordt dan
        weer verwijderd.
    """
    storage = tiles_storage()
    with open(local_path, "rb") as fh:
        saved = storage.save(key, File(fh, name=key))
    if saved != key:
        storage.delete(saved)
        raise ImproperlyConfigured(
            f"rgs_django_spatial: de tiles-storage sloeg {key!r} op als {saved!r}. Zet de storage op "
            "overschrijven (FileSystemStorage: allow_overwrite=True; FsspecStorage: on_collision='overwrite')."
        )
    os.remove(local_path)


def delete_pmtiles(key: str) -> None:
    """Verwijder het object ``key`` uit de tiles-storage (idempotent)."""
    tiles_storage().delete(key)


def pmtiles_url(key: str) -> str:
    """URL waarop de browser ``key`` laadt: presigned als de storage dat kan, anders ``url()``.

    Parameters
    ----------
    key : str
        Objectnaam binnen de tiles-storage.

    Returns
    -------
    str
        ``storage.url_signed(key, expires=TILES_URL_TTL)`` als de storage die
        methode heeft en geen ``NotImplementedError`` gooit; anders
        ``storage.url(key)``.
    """
    storage = tiles_storage()
    url_signed = getattr(storage, "url_signed", None)
    if url_signed is not None:
        ttl = int(getattr(settings, "TILES_URL_TTL", DEFAULT_URL_TTL))
        try:
            return url_signed(key, expires=ttl)
        except NotImplementedError:
            pass
    return storage.url(key)


def read_object(key: str) -> bytes:
    """Lees een opgeslagen object (bv. een geserveerd ``.geojson``) uit de tiles-storage.

    Bedoeld voor kleine bestanden die Django zelf streamt (i.t.t. PMTiles, die de
    browser via :func:`pmtiles_url` rechtstreeks ophaalt).

    Raises
    ------
    FileNotFoundError
        Als het object niet bestaat.
    """
    storage = tiles_storage()
    if not storage.exists(key):
        raise FileNotFoundError(key)
    with storage.open(key, "rb") as f:
        return f.read()
