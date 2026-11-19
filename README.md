# RGS django spatial


Datamodel en functies om met (configureerbare) kaarten in de frontend te werken.

## Toegang: algemeen of van één eigenaar

Bronnen, lagen, thema's, stijlen en kleurensets zijn **algemeen**
(`access_through = authenticated`), van **één eigenaar** (`organisation` + `access_id`) of
van **één project** (`project` + `access_id`). De consumer bepaalt wie wat mag; het pakket
kent zijn organisatie- en projectmodel niet.

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
- `SPATIAL_RESTRICT_READ = True`: de Hasura-select van bronnen, lagen, thema's, stijlen,
  kleurensets en de koppeltabellen toont alleen algemene rijen en rijen van de actieve
  organisatie (`x-hasura-org-id`); staf blijft `{}`. De kaart-kaartlaag volgt haar laag,
  de stijlkoppeling heeft een eigen scope én volgt haar laag.
- Stijlen per organisatie (urbanworks#433): een organisatie hangt eigen stijlkoppelingen
  aan een applicatiebrede laag, als extra stijl of als variant die een standaardstijl
  vervangt (`spatial_layer_style.vervangt`, `standaard`); zie de docstring van
  `models/spatial_layer_style.py` en `CHANGELOG.md` 0.12.0.
- **Projectniveau** (waterworks#548): een rij kan ook van één project zijn
  (`access_through = project`, `access_id` = project-id). Het pakket kent het projectmodel
  en de projectrollen van de consumer niet; zonder de settings hieronder ziet en beheert
  alleen staf zulke rijen via Hasura.
  - `SPATIAL_PERMISSIONS_HOOK = "pad.naar.functie"`: callable `(tabel) -> {rol: {actie:
    filter}}`. Elke rol die hij teruggeeft krijgt op die tabel die Hasura-regel (en
    vervangt een regel van het pakket voor dezelfde rol). Het app-rijfilter van bron en
    laag komt er vanzelf bij op update en delete.
  - `SPATIAL_EXTRA_SCHRIJFROLLEN = ["proj_man"]`: deze rollen krijgen op `access_through`,
    `access_id`, `spatial_layer_style.vervangt` en `spatial_source.authentication_config`
    hetzelfde kolommasker als `org_adm`. **Let op:** geef zo'n rol op `spatial_source` dan
    een eigen select-filter dat alleen de rijen toont die hij mag beheren, anders leest hij
    de credentials van elke bron die hij mag zien.
  - `SpatialAccess` heeft erbij: `lees_project_ids`, `schrijf_project_ids` en
    `lees_org_ids_via_project` (zie hieronder).
  - De relatie van `access_id` naar het project (voor een Hasura-filter via de rechtentabel)
    en het opruimen bij het verwijderen van een project regelt de consumer: het pakket legt
    geen foreign key naar een model dat het niet kent.
- **`zichtbaarheid`** op bron, laag en thema (alleen van betekenis bij scope organisatie):
  `organisatie_leden` of `organisatie_projecten` (standaard, ook voor bestaande rijen). Met
  `organisatie_projecten` mag ook wie een project van die organisatie leest de rij zien:
  in `SpatialAccess` via `lees_org_ids_via_project`, in Hasura via de hook.
- Stijlen per project: een projectrij in `spatial_layer_style` werkt als een
  organisatierij en mag via `vervangt` een applicatiebrede rij of een organisatierij
  vervangen. Volgorde bij het oplossen: project, organisatie, applicatiebreed.
- Zet geen geheime sleutels in een URL in `source_config`: die is voor elke rol die de
  rij leest zichtbaar. Credentials horen in `authentication_config`.
- `GET /mapproxy-config.yaml` filtert bewust niet: de MapProxy-sidecar heeft geen
  gebruiker en heeft de upstream van alle reproject-bronnen nodig. Schermt de consumer
  zelf af (netwerk) en mount hem niet onder een publieke router.

## Stijlen valideren (`rgs_django_spatial.stijl`)

`SpatialStyle.config` volgt het stijlmodel v3 van `@getthepointgit/map`. Controleer een
geseede stijl voordat je hem wegschrijft; een fout komt anders pas in de browser uit:

```python
from rgs_django_spatial.stijl import valideer_stijl_config

fouten = valideer_stijl_config(config, kleurenset_ids={str(k.id) for k in kleurensets})
if fouten:
    raise CommandError(f"Stijl {naam} is ongeldig: {'; '.join(fouten)}")
```

`stijl.schalen` heeft de bouwstenen voor stijldefinities (`zoom`, `stops`, kleurenramps),
`stijl.conversie` zet een v2-config om naar v3.

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
