# rgs-django-spatial: notities voor Claude

Dit bestand wordt geladen als Claude in deze repo werkt. Het bevat wat niet uit de code volgt.
Consumers (`waterworks`, `urbanworks`, `drainworks`) hebben een eigen `CLAUDE.md`.

## Wat dit is

Django-pakket met het datamodel en de routes voor configureerbare kaarten: bronnen, lagen, thema's,
stijlen, kleurensets en hun koppeltabellen (`rgs_django_spatial/models/`), de Django-Ninja-routes
(`api.py`), tegels en PMTiles (`tiles/`), de MapProxy-config (`mapproxy.py`) en de validatie van het
stijlmodel v3 (`stijl/`). Het bouwt op `rgs-django-utils` (`Config(...)` per veld, Hasura-metadata).
De functionele uitleg staat in `README.md`; lees die vóór je aan rechten of scope komt.

## Werkwijze

- **Eerst een branch.** Nooit op `main`. Werk in een eigen git-worktree: de backends van de consumers
  gebruiken deze repo als editable path-dep (`../../rgs-django-spatial`), dus de hoofdcheckout blijft
  op `main` staan.
- **Niet zelfstandig pushen.** Alleen lokale commits; `git push`, `gh pr create` en tags op opdracht.
  Mergen gaat met squash: de PR-titel wordt het commit-onderwerp.
- **Lint zoals CI:** `ruff format --check .` en `ruff check .` met ruff 0.16.3 (dezelfde pin als de
  CI-job `lint`). Herstellen: `pixi run style`. De kernregels staan in `ruff-gedeeld.toml`, een kopie
  van de gedeelde config uit `GetThePointGit/rgs-dev-config`: wijzig die kopie niet met de hand maar
  met `rgs-config sync-ruff .`. Uitzonderingen voor deze repo horen in `pyproject.toml`.
- **Tests:** `pixi run tests` (pytest met `tests/testapp`, instellingen in
  `tests/testapp/settings_test.py`). Een test wordt niet aangepast om hem groen te krijgen:
  onderzoek eerst de oorzaak en doe een voorstel.
- **Docstrings in NumPy-stijl** voor publieke functies en methoden; ruff dwingt het af.
- Commentaar, docstrings en `verbose_name`s zijn Nederlands.

## Patronen en valkuilen

- **Het pakket kent het organisatie- en projectmodel van de consumer niet.** Scope loopt via
  `access_through` (`authenticated`, `organisation`, `project`) plus `access_id`, zonder foreign key.
  Wie wat mag komt van de consumer via de settings `SPATIAL_ACCESS_RESOLVER`,
  `SPATIAL_PERMISSIONS_HOOK`, `SPATIAL_EXTRA_SCHRIJFROLLEN` en `SPATIAL_RESTRICT_READ`. Leid in dit
  pakket nooit rechten af uit een organisatie van de gebruiker.
- **Zonder die settings blijft het gedrag ongewijzigd.** Een nieuwe beperking is optioneel en staat
  standaard uit, zodat een consumer die niets instelt niets merkt van een upgrade.
- **Een kapot pad in zo'n setting geeft een `ImportError`**, nooit stil "alles mag".
- **Credentials horen in `authentication_config`**, niet in een URL in `source_config`: die laatste
  ziet elke rol die de rij leest.
- **Een modelwijziging raakt de Hasura-metadata en het JSON-schema van elke consumer.** Noem in de
  changelog wat de consumer na de upgrade moet doen (migratie, metadata genereren, seed draaien).
- **Migraties** gaan uit van een bepaalde versie van `rgs-django-utils` (bv. `0013` van 0.19.0);
  noem die afhankelijkheid in de changelog.
- **Het stijlmodel v3 heeft een spiegel in `@getthepointgit/map`** (`rgs-ui-stack`). Een wijziging in
  `stijl/validatie.py` zonder dezelfde wijziging daar geeft stijlen die de server goedkeurt en de
  browser weigert, of andersom.

## Release

1. Versie ophogen in `pyproject.toml`.
2. Sectie in `CHANGELOG.md` (`## x.y.z (JJJJ-MM-DD)`), met wat de consumer moet doen.
3. PR, CI groen, squash-merge.
4. Op opdracht: tag `vX.Y.Z` zetten en pushen. Consumers pinnen op die tag in hun `pixi.toml`.
