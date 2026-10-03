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
