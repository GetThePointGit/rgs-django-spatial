# Wijzigingen

## 0.10.0 (2026-11-06)

### Gewijzigd
- **Tiles-opslag via Django `STORAGES`** (#27, epic waterworks#757). `rgs_django_spatial.tiles.storage`
  gebruikt een gewone Django-storage, standaard `storages["tiles"]` (alias instelbaar met
  `SPATIAL_TILES_STORAGE_ALIAS`), en kent zelf geen S3 meer: `store_pmtiles` → `storage.save`
  (de storage moet op overschrijven staan, anders `ImproperlyConfigured`), `delete_pmtiles` →
  `storage.delete`, `read_object` → `storage.open`, `pmtiles_url` → `storage.url_signed(key,
  expires=TILES_URL_TTL)` als de storage dat biedt (`FsspecStorage` op S3), anders `storage.url`.
  Consumers zetten in `settings.py`:

  ```python
  # lokaal (dev): bestanden onder VAR_DIR/tiles, geserveerd op /tiles/
  STORAGES["tiles"] = {
      "BACKEND": "django.core.files.storage.FileSystemStorage",
      "OPTIONS": {"location": VAR_DIR / "tiles", "base_url": "/tiles/", "allow_overwrite": True},
  }
  # S3 (gehost): private bucket, presigned GET-URL's
  STORAGES["tiles"] = {
      "BACKEND": "django_fsspec.FsspecStorage",
      "OPTIONS": {
          "on_collision": "overwrite",
          "storage_config": {
              "protocol": "s3", "key": S3_ACCESS_KEY, "secret": S3_SECRET_KEY,
              "endpoint_url": "https://s3.nl-ams.scw.cloud",
              "client_kwargs": {"region_name": "nl-ams"},
              "relative_to_path": f"{S3_BUCKET_TILES}/{S3_TILES_PREFIX}",
          },
      },
  }
  ```

  Daarmee kunnen media en tiles dezelfde credentials en dezelfde `django_fsspec`-configuratie
  delen, en wordt de s3fs-afhankelijkheid nog maar op één plek (django-fsspec) bewaakt.
- **Overgangsregeling, één release:** ontbreekt de alias maar staan `TILES_STORAGE`/`TILES_S3`
  (en `VAR_DIR`) er nog, dan bouwt de module daar intern een gelijkwaardige `FsspecStorage`
  van en geeft een `DeprecationWarning`. Daarvoor moet django-fsspec geïnstalleerd zijn (bij
  waterworks en urbanworks al zo voor media). `TILES_URL_TTL` blijft.
- `pixi.toml` (alleen dev/CI): django-fsspec erbij, ondergrens `s3fs >= 2026.6.0`
  (presign-geheugenlek s3fs#1019, zie django-fsspec#14 en urbanworks#408).

### Verwijderd
- `tiles_backend()`, `local_pmtiles_path()`, `_tiles_key()`, `_s3fs()` en `_s3_object_path()`
  uit `tiles.storage`; de consumers (waterworks, urbanworks) gebruikten alleen de vier
  publieke functies, die ongewijzigd van signatuur zijn.

## 0.9.2 (2026-11-06)

### Gewijzigd
- Gedeelde dev-config uit `GetThePointGit/rgs-dev-config` (rgs-ui-stack#305, #23). De
  ruff-kernregels staan in `ruff-gedeeld.toml` (kopie, `pyproject.toml` extendt hem);
  lokaal blijft alleen `extend-exclude`. Gevolgen: `D401` wordt genegeerd (Nederlandse
  docstrings) en `F403` erbij voor `__init__.py`. Verder `.editorconfig`, Dependabot
  voor GitHub Actions en de herbruikbare workflow `dev-config-check.yml` in CI. Geen
  codewijziging.
- `pixi.toml`: `python-dateutil = "<3"` in de conda-dependencies en `s3fs = ">=2024.2.0"`.
  Een verse solve koos sinds kort python-dateutil 4.x, waardoor botocore (via s3fs →
  aiobotocore) niet paste en de pypi-solve terugviel op `s3fs==0.3.5` (sdist die niet
  bouwt op Python 3.12). Alleen de ontwikkel-/CI-omgeving; de library-eisen in
  `pyproject.toml` veranderen niet.

## 0.9.1 (2026-10-19)

### Gewijzigd
- `default_auto_field = "django.db.models.BigAutoField"` op de AppConfig (#16). De
  migraties zijn met `BigAutoField` gegenereerd; tot nu toe hing het pk-type van
  `SpatialMap` af van `DEFAULT_AUTO_FIELD` in de settings van het project, waardoor
  een project met `AutoField` (drainworks) een `0010_alter_spatialmap_id` voorgesteld
  kreeg. Geen nieuwe migratie; voor waterworks en urbanworks (`BigAutoField`) verandert
  er niets. CI controleert `makemigrations --check` nu ook met `AutoField` als
  projectstandaard.

## 0.9.0 (2026-10-06)

### Toegevoegd
- Bescherming van **app-rijen** (urbanworks#252): een bron met de sleutel `app_layer` in
  `source_config`, of een laag met `app_layer` in `params`, kan niet meer worden
  gewijzigd of verwijderd.
  - Hasura: de update- en delete-rechten van elke rol (ook `sys_adm`) krijgen het filter
    `geen_app_rij(kolom)`. Select en insert blijven gelijk.
  - Django: `pre_save`/`pre_delete`-guards (`AppLaagBeschermd`, een `PermissionDenied`) weigeren
    wijzigen en verwijderen van een bestaande app-rij en het aanmaken van een nieuwe, ook via
    `QuerySet.delete()`. `QuerySet.update()` en ruwe SQL worden niet gedekt.
  - Nieuw: `rgs_django_spatial/app_lagen.py` (`is_app_laag`, `is_app_bron`, `geen_app_rij`,
    `app_laag_onderhoud`) en `apps.py` (sluit de signals aan).

### Let op bij upgraden
- Apps moeten hun **Hasura-metadata opnieuw genereren**: de permissiefilters zijn gewijzigd.
- Seeds en andere code die met de echte modellen app-rijen aanmaken, wijzigen of verwijderen
  moeten binnen `with app_laag_onderhoud():` draaien, anders volgt `AppLaagBeschermd`.
  Een migratie met `RunPython` die `apps.get_model` gebruikt werkt op historische modellen,
  waarop de guard niet aanslaat: daar is de bypass niet nodig.
- Bestaande app-rijen zijn direct na de upgrade beschermd. Een seed die app-rijen schrijft
  (bv. `update_or_create`) moet dus in dezelfde deploy `app_laag_onderhoud()` krijgen.

### Bekende beperking
- Een insert via Hasura van een rij met `app_layer` blijft toegestaan (het insert-filter is
  ongewijzigd). Zo'n rij kan daarna via Hasura niet meer worden gewijzigd of verwijderd.
- Zonder app-rijen verandert er niets voor bestaande data. Geen nieuwe migratie.

## 0.8.0 (2026-10-03)

### Toegevoegd
- Optionele toegangsregeling voor bronnen, lagen en thema's (algemeen of van één
  eigenaar): `SPATIAL_ACCESS_RESOLVER` (callable `request -> SpatialAccess`) voor de
  routes in `api.py`, en `SPATIAL_RESTRICT_READ` voor een leesfilter op de
  Hasura-select (algemeen OF actieve organisatie). Zie de README.
- `POST /capabilities/` vereist schrijfrecht zodra een resolver is ingesteld.

### Ongewijzigd
- Zonder deze twee settings is het gedrag gelijk aan v0.7.0: geen nieuwe migratie en
  geen permissiewijziging (ook niet voor stijlen en kleurensets; scope daarvoor
  volgt in #17).
