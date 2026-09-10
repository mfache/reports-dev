# Tests `reports`

Suite `pytest` remplaçant les anciens scripts de débogage ponctuels
(`test_bottle_*.py`, `test_mount.py`, `test_server.py`, `test_uwsgi.py` —
retirés lors de la refonte, aucune assertion, juste des `print()` à
relire à la main).

## Exécuter les tests

```bash
./run_tests.sh
```

**Important** : ce script s'exécute avec `sudo -u mariadb`, car
`/etc/boitier-fleet/db-dev.env` (et `db.env` en production) n'est lisible
que par ce compte — exactement les mêmes droits que le vrai process
uwsgi. Lancer `pytest` directement en tant que `marc`/`docsadmin` sans
passer par `run_tests.sh` échouera silencieusement sur tout ce qui touche
la base (le fichier d'environnement redevient introuvable, `core.config`
retombe sur les identifiants par défaut).

Le venv et la base de données utilisés sont déduits du nom du dossier
courant (`reports-dev` ici → `/opt/venv/reports-dev` + `dt_dev` ;
`reports` en production → `/opt/venv/reports` + `dt`). Ce n'est **jamais**
la vraie base `dt` de production qui est utilisée en dev.

## Organisation

- `conftest.py` — ajoute `src/` au chemin d'import, fixe
  `REPORTS_BASE_PATH`/`DB_ENV_FILE` par défaut, fournit les fixtures
  `wsgi_app`/`base_path`.
- `_helpers.py` — `call_wsgi(app, path, ...)` : appelle l'application WSGI
  directement (comme le fait uwsgi), sans lancer de serveur réseau réel.
  Plus fidèle qu'un test qui invoquerait les fonctions de route
  directement — c'est justement l'absence de ce type de test qui a laissé
  passer l'incident du 10 septembre où l'UI n'était pas montée.
- `test_wsgi_mount.py` — non-régression directe de cet incident, plus un
  garde-fou sur le nombre de routes enregistrées.
- `test_core_paths.py` — non-régression du bug où `ui.py` pointait en dur
  vers les fichiers de production.
- `test_pwa_exemptions.py` — non-régression de l'incident CSRF/Service
  Worker du 10 septembre.
- Un fichier par domaine `services/` (`test_fleet.py`, `test_chantiers.py`,
  `test_sync.py`, `test_trends.py`, `test_logs.py`, `test_headscale.py`,
  `test_templates_maintenance.py`) : couvrent au minimum le refus (401/403)
  sans authentification, et pour `fleet.py` un cycle complet
  d'enregistrement contre `dt_dev`.

## Limites connues

Ces tests couvrent le contrat HTTP (routage, authentification, formats de
réponse), pas la logique métier fine à l'intérieur de chaque route
(actuellement inline dans les fonctions de route — voir
`CAHIER-DES-CHARGES-REFONTE.md` §9 pour la nuance assumée sur la
séparation logique/routage). Les routes SSE (`web/stream.py`) ne sont pas
testées ici : elles dépendent d'une connexion MQTT réelle et d'un flux
bloquant, peu adaptées à un test unitaire rapide.
