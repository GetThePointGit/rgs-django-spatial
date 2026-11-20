# Wijzigingen

## 0.14.0 (2026-11-20)

### Gewijzigd
- **Nederlandse veldnamen** (waterworks#320). De `verbose_name`s die nog Engels waren zijn
  vertaald: "brontype", "bronconfiguratie", "GeoJSON-bestand", "tegelstatus",
  "foutmelding tegels", "tegels bijgewerkt op", "begrenzing", "minimaal zoomniveau",
  "maximaal zoomniveau" en "configuratievelden". De enum-tabellen heten "type kaartbron" en
  "authenticatietype kaartbron". Migratie `0013_nederlandse_veldnamen` wijzigt alleen
  `verbose_name`s (geen SQL) en gaat uit van rgs-django-utils 0.19.0, waar `BaseEnum.name`
  "naam" heet.

## 0.13.0 (2026-11-19)

### Toegevoegd
- **`rgs_django_spatial.stijl`** (#22): de Python-validatie van het stijlmodel v3, verhuisd uit
  waterworks (`core/kaartlagen`), zodat elke consumer zijn geseede stijlen kan controleren
  voordat hij ze wegschrijft:
  - `stijl.validatie.valideer_stijl_config(config, kleurenset_ids=...)` geeft de lijst fouten
    (leeg = geldig). Spiegel van de validator in `@getthepointgit/map`, op drie punten
    bewust strenger (zie de module-docstring);
  - `stijl.schalen`: `zoom`, `stops`, `RAMP_BLAUW`, `RAMP_AMBER` en de vaste kleurschalen
    `jaarschaal_rdylgn`, `jaarschaal_inmeten` en `toetsklasseschaal`;
  - `stijl.conversie`: `converteer_naar_v3` en `is_v3` voor v2-configuraties.

  Geen gedragswijziging ten opzichte van de waterworks-versie, geen migratie. Consumers die de
  modules zelf hadden, halen hun kopie weg en importeren uit de lib.

## 0.12.0 (2026-11-19)

### Toegevoegd
- **Scope op stijlen en kleurensets** (urbanworks#433, #17). `spatial_style` en
  `spatial_kleurenset` krijgen `access_through` + `access_id`, met dezelfde rechten als laag,
  bron en thema: `org_adm` muteert alleen rijen van de actieve organisatie, staf alles; lezen
  is met `SPATIAL_RESTRICT_READ` beperkt tot applicatiebreed plus de actieve organisatie.
  Een applicatiebrede stijl of kleurenset is voor `org_adm` dus alleen-lezen.
- **Eigen scope op de stijlkoppeling** (`spatial_layer_style`). Op een organisatielaag volgt
  een koppelrij altijd de laag. Op een applicatiebrede laag (ook de app-laag) mag een
  organisatie eigen koppelrijen hangen:
  - `vervangt` (FK naar een applicatiebrede koppelrij van dezelfde laag): deze rij is de
    variant van die standaardstijl voor de organisatie. Hoogstens één variant per
    standaardrij per organisatie; verdwijnt de variant, dan geldt de standaardrij weer, en
    verdwijnt de standaardrij, dan verdwijnen de varianten mee (`CASCADE`);
  - zonder `vervangt` is het een extra stijl van de organisatie;
  - `standaard` (boolean): de voorgeselecteerde stijl binnen een scope, hoogstens één per
    laag per scope. Zonder zo'n rij blijft `spatial_map_layer.default_style` gelden;
    `standaard_in` (moduleletters) is ongewijzigd.

  Welke rijen voor een gebruiker gelden lost de client op (`@getthepointgit/map`):
  applicatiebreed plus de actieve organisatie, min de vervangen standaardrijen.
- De regels zitten in `SpatialLayerStyle.clean()`/`save()`, in constraints en, omdat Hasura
  Django omzeilt, in de trigger `spatial_layer_style_scope` (alleen PostgreSQL): scope volgt
  een organisatielaag, een organisatiestijl hoort bij de organisatie van de koppelrij, en
  `vervangt` wijst naar een applicatiebrede rij van dezelfde laag.
- `upgrade_laag_naar_applicatiebreed` neemt de stijlkoppelingen van de laag mee, met hun
  stijlen en de kleurensets waar die naar verwijzen (`stijlen_omgezet` in het resultaat).
- CI draait de suite ook op PostgreSQL (`tests/testapp/settings_postgres.py`).

- **Projectniveau in de scope** (waterworks#548). `access_through = project` met het
  project-id in `access_id`, op bron, laag, thema, stijl, kleurenset en stijlkoppeling.
  - `SPATIAL_PERMISSIONS_HOOK` (callable `tabel -> {rol: {actie: filter}}`): de consumer
    geeft per tabel extra rollen met een eigen lees- en schrijffilter mee, bijvoorbeeld
    projectrollen via zijn rechtentabel. `scoped_table_permissions` heeft daarvoor de
    parameter `tabel`.
  - `SPATIAL_EXTRA_SCHRIJFROLLEN`: rollen die op de scope-kolommen, `vervangt` en
    `authentication_config` het kolommasker van `org_adm` krijgen (`scope_fperm`).
  - `SpatialAccess`: `lees_project_ids`, `schrijf_project_ids`, `lees_org_ids_via_project`;
    `lees_filter(met_zichtbaarheid=True)`.
  - Stijlkoppeling: op een projectlaag volgt een koppelrij de laag; op een organisatielaag
    ook, behalve een projectrij. Een projectrij mag via `vervangt` een applicatiebrede rij
    of een organisatierij vervangen; een rij die zelf iets vervangt is niet vervangbaar. Een
    projectstijl hoort alleen bij een rij van dat project.
  - Zonder de settings verandert er niets: geen extra rol, geen extra filter.
  - Het pakket legt geen foreign key naar het projectmodel van de consumer. De Hasura-relatie
    van `access_id` naar het project en het opruimen bij verwijderen regelt de consumer.
- **`zichtbaarheid`** op bron, laag en thema (`enum_map_zichtbaarheid`):
  `organisatie_leden` of `organisatie_projecten`. Alleen van betekenis bij scope organisatie;
  bestaande rijen krijgen `organisatie_projecten`. Het pakket slaat de keuze op; de consumer
  dwingt hem af via de hook en `lees_org_ids_via_project`.

### Gewijzigd
- De constraints `spatial_layer_style_vervanger_per_org` en
  `spatial_layer_style_vervangt_alleen_org` heten nu `..._vervanger_per_scope` (uniek op
  `vervangt` + scope) en `..._vervangt_met_scope` (organisatie of project).
- `unique_layer_style` (laag + stijl) is vervangen door `unique_layer_style_per_scope`
  (laag + stijl + scope): een organisatierij mag dezelfde stijl gebruiken als een
  standaardrij.
- Hasura: de rechten op `spatial_layer_style` hangen niet meer aan de laag maar aan de rij
  zelf. De insert-check van `org_adm` eist de eigen scope én een laag die applicatiebreed of
  van de eigen organisatie is.

### Migratie (`0011_stijl_scope`)
- Bestaande koppelrijen krijgen de scope van hun laag. Bestaande stijlen en kleurensets
  worden applicatiebreed, behalve als ze uitsluitend door lagen van precies één organisatie
  worden gebruikt: die gaan naar die organisatie. Er wordt niets verwijderd of gekopieerd.
- Na het bijwerken: migreren en de Hasura-metadata opnieuw genereren/toepassen.
- **Let op voor consumers:** een `org_adm` kan een applicatiebrede stijl of kleurenset daarna
  niet meer wijzigen, en een insert zonder scope wordt applicatiebreed en dus geweigerd. De
  stijlen- en kleurensetsdialoog sturen de scope mee vanaf de `@getthepointgit/map`-versie
  die bij urbanworks#433 hoort; bump die tegelijk. Een koppelrij op een organisatielaag
  krijgt de scope van de laag van de trigger, ook van een client die niets meestuurt.

### Migratie (`0012_project_scope`)
- Maakt `enum_map_zichtbaarheid` met zijn twee rijen, voegt `zichtbaarheid` toe, vervangt de
  twee constraints en de functie achter de trigger `spatial_layer_style_scope`. Bestaande
  rijen veranderen niet van scope.
- Na het bijwerken: migreren en de Hasura-metadata opnieuw genereren/toepassen.

## 0.11.0 (2026-11-06)

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
