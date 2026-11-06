# RGS django spatial


Datamodel en functies om met (configureerbare) kaarten in de frontend te werken.

## Toegang: algemeen of van één eigenaar

Bronnen, lagen en thema's zijn **algemeen** (`access_through = authenticated`) of van
**één eigenaar** (`organisation` + `access_id`). De consumer bepaalt wie wat mag; het
pakket kent zijn organisatiemodel niet. Stijlen en kleurensets hebben (nog) geen scope:
die volgt in rgs-django-spatial#17.

Beide settings zijn optioneel. **Zonder deze settings is het gedrag ongewijzigd**: geen
extra filter op de routes in `api.py`, geen rijfilter op de Hasura-select, en er is geen
migratie of permissiewijziging bij gekomen.

- `SPATIAL_ACCESS_RESOLVER = "pad.naar.functie"`: callable `(request) -> SpatialAccess`
  (`rgs_django_spatial.access`). Velden van `SpatialAccess`:
  `lees_org_ids` (eigenaars die naast de algemene rijen leesbaar zijn),
  `schrijf_org_ids` (eigenaars die schrijfbaar zijn), `schrijf_algemeen` (algemene rijen
  wijzigen), `lees_alles` (alle rijen lezen, van elke eigenaar; typisch staf) en
  `schrijf_alles` (elke leesbare rij schrijven; typisch staf). Schrijven vereist altijd
  dat de rij ook leesbaar is. De resolver wordt per verzoek één keer aangeroepen en
  onthouden; een kapot pad geeft een `ImportError` (nooit stil "alles mag").
  De routes in `api.py` lezen er algemeen + `lees_org_ids` mee,
  en schrijven (upload, genereer-tiles, upload-geojson) alleen bij schrijfrecht
  (404 voor onleesbare, 403 voor leesbare maar niet schrijfbare bronnen).
  `POST /capabilities/` vereist enig schrijfrecht. `GET /{id}/geojson/` eist dan
  een leesbare bron in de DB.
- `SPATIAL_RESTRICT_READ = True`: de Hasura-select van bronnen, lagen, thema's en de
  koppeltabellen (via hun laag) toont alleen algemene rijen en rijen van de actieve
  organisatie (`x-hasura-org-id`); staf blijft `{}`. Stijlen en kleurensets blijven
  ongefilterd.
- Zet geen geheime sleutels in een URL in `source_config`: die is voor elke rol die de
  rij leest zichtbaar. Credentials horen in `authentication_config`.
- `GET /mapproxy-config.yaml` filtert bewust niet: de MapProxy-sidecar heeft geen
  gebruiker en heeft de upstream van alle reproject-bronnen nodig. Schermt de consumer
  zelf af (netwerk) en mount hem niet onder een publieke router.

## Tiles-opslag (`STORAGES["tiles"]`)

De PMTiles en geserveerde GeoJSON van `rgs_django_spatial.tiles` staan in een gewone
Django-storage, standaard de alias `tiles` in `settings.STORAGES` (anders:
`SPATIAL_TILES_STORAGE_ALIAS`). De storage moet overschrijven toestaan en `url()` moet
het pad geven waar de browser de tiles laadt. Heeft de storage `url_signed()` (zoals
`django_fsspec.FsspecStorage` op S3), dan krijgt de browser presigned URL's met een
geldigheid van `TILES_URL_TTL` seconden (default 86400).

```python
# lokaal: bestanden onder VAR_DIR/tiles, geserveerd op /tiles/ (bv. nginx-sidecar)
STORAGES["tiles"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"location": VAR_DIR / "tiles", "base_url": "/tiles/", "allow_overwrite": True},
}

# S3: private bucket, presigned GET-URL's (range-requests vanuit de browser → CORS op de bucket)
STORAGES["tiles"] = {
    "BACKEND": "django_fsspec.FsspecStorage",
    "OPTIONS": {
        "on_collision": "overwrite",
        "storage_config": {
            "protocol": "s3",
            "key": S3_ACCESS_KEY,
            "secret": S3_SECRET_KEY,
            "endpoint_url": "https://s3.nl-ams.scw.cloud",
            "client_kwargs": {"region_name": "nl-ams"},
            "relative_to_path": f"{S3_BUCKET_TILES}/{S3_TILES_PREFIX}",
        },
    },
}
```

De oude settings `TILES_STORAGE`/`TILES_S3`/`VAR_DIR` werken nog één release (met
`DeprecationWarning`, django-fsspec vereist); zie `CHANGELOG.md` 0.11.0.

## Codestijl en dev-config

De ruff-kernregels staan in `ruff-gedeeld.toml`, een byte-gelijke kopie van de gedeelde
config uit `GetThePointGit/rgs-dev-config` (afspraken: `docs/dependencies.md` daar). Niet
in de kopie bewerken; bijwerken met `rgs-config sync-ruff .`. Repo-eigen uitzonderingen
horen in `pyproject.toml` (`extend-exclude`, `extend-per-file-ignores`). CI draait
`rgs-config check --strict` via de herbruikbare workflow `dev-config-check.yml`.
