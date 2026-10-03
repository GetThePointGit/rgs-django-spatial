# Wijzigingen

## Unreleased

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
