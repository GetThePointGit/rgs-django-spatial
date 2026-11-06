# Wijzigingen

## 0.10.0 (2026-11-06)

### Toegevoegd
- `SpatialLayer.legend_url` (optioneel, migratie `0010_spatiallayer_legend_url`): URL van een
  vaste legenda-afbeelding voor bronnen die zelf geen legenda leveren (bijv. een ArcGIS
  ImageServer); de kaartlegenda in `@getthepointgit/map` toont die onder de laag
  (urbanworks#168). Rechten als de andere laagvelden: lezen voor elke ingelogde gebruiker,
  schrijven volgens de bestaande tabelregel (`org_adm` eigen organisatie, staf alles). Na
  het bijwerken: migreren en de Hasura-metadata opnieuw genereren/toepassen.

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
