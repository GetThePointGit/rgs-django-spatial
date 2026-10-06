# Wijzigingen

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
