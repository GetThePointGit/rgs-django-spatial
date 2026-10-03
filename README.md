# RGS django spatial


Datamodel en functies om met (configureerbare) kaarten in de frontend te werken.

## Toegang: algemeen of van één eigenaar

Bronnen, lagen, thema's, stijlen en kleurensets zijn **algemeen**
(`access_through = authenticated`) of van **één eigenaar** (`organisation` +
`access_id`). De consumer bepaalt wie wat mag; het pakket kent zijn organisatiemodel niet.
Beide settings zijn optioneel; zonder is het gedrag ongewijzigd.

- `SPATIAL_ACCESS_RESOLVER = "pad.naar.functie"`: callable `(request) -> SpatialAccess`
  (`rgs_django_spatial.access`) met `lees_org_ids`, `schrijf_org_ids` en
  `schrijf_algemeen`. De routes in `api.py` lezen er algemeen + `lees_org_ids` mee,
  en schrijven (upload, genereer-tiles, upload-geojson) alleen bij schrijfrecht
  (404 voor onleesbare, 403 voor leesbare maar niet schrijfbare bronnen).
  `POST /capabilities/` vereist enig schrijfrecht. `GET /{id}/geojson/` eist dan
  een leesbare bron in de DB.
- `SPATIAL_RESTRICT_READ = True`: de Hasura-select van de scope-tabellen toont alleen
  algemene rijen en rijen van de actieve organisatie (`x-hasura-org-id`).
- `GET /mapproxy-config.yaml` filtert bewust niet: de MapProxy-sidecar heeft geen
  gebruiker en heeft de upstream van alle reproject-bronnen nodig. Schermt de consumer
  zelf af (netwerk) en mount hem niet onder een publieke router.
