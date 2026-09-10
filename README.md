# Projet `reports` — API de flotte et UI web (Deltathermic)

`reports` est le serveur central de la flotte de boîtiers de
télémaintenance `rpinode` : réception des synchronisations, gestion des
chantiers, des templates Modbus/BACnet partagés, intégration Headscale,
et l'interface web d'administration correspondante. Servi par
`docs.deltathermic.be` via uWSGI + nginx.

Depuis le 10 septembre 2026, le projet suit une refonte progressive vers
une architecture modulaire inspirée de `rpinode` (voir
[`CAHIER-DES-CHARGES-REFONTE.md`](CAHIER-DES-CHARGES-REFONTE.md) pour le
détail, les décisions en attente et l'état d'avancement).

## Architecture

- `app.py` : point d'entrée WSGI (`module = app:application` dans
  `reports.ini`). Monte `api_app` sous `<BASE_PATH>/api` et `ui_app` sous
  `<BASE_PATH>` (`BASE_PATH` vaut `/reports` par défaut, surchargeable via
  `REPORTS_BASE_PATH` — c'est ce qui permet à l'interface de dev de
  tourner sur le même code sans jamais répondre sous `/reports`).
- `src/core/` : fondations — `config.py` (lecture de
  `/etc/boitier-fleet/db*.env` et de `BASE_PATH`), `database.py`
  (connexion MariaDB), `paths.py` (chemins absolus `templates/`, `static/`,
  `webdav/`, calculés depuis l'emplacement réel du code — jamais en dur).
- `src/services/` : logique métier de l'API, par domaine — `fleet.py`
  (authentification boîtier, enregistrement), `chantiers.py` (résolution
  de chantier par antenne GSM), `sync.py` (route `/sync`),
  `trends.py`, `logs.py`, `headscale.py`, `templates_maintenance.py`.
- `src/web/` : assemblage des applications Bottle — `api.py` (routes
  transverses `/usage`, gestion d'erreurs, importe `services/*` pour
  enregistrement de leurs routes), `ui.py` (l'essentiel des pages),
  `stream.py` (les 2 routes SSE), `responses.py` (`json_ok`/`json_error`).

  **Nuance assumée** (voir §9 du cahier des charges) : chaque route garde
  sa logique métier et ses requêtes SQL inline — la séparation stricte
  « services sans aucune dépendance à Bottle » est reportée tant qu'il
  n'existe pas de suite de tests assez large pour rattraper une
  régression subtile lors d'une réécriture aussi profonde.
- `templates/` : vues Bottle (`SimpleTemplate`, `.tpl`).
- `static/` : JS/CSS/icônes/manifest/service worker.
- `webdav/` : point de montage nginx pour les scripts (scanner, pdfsync),
  sans rapport avec le code Python.
- `docs/` : documentation technique — voir
  [`docs/README.md`](docs/README.md).
- `tools/` : scripts annexes par usage — voir
  [`tools/README.md`](tools/README.md).
- `tests/` : suite `pytest` — voir [`tests/README.md`](tests/README.md).

## Exécuter les tests

```bash
./run_tests.sh
```

Doit s'exécuter avec les mêmes droits que le vrai process uwsgi
(`sudo -u mariadb` — le script le fait automatiquement), car
`/etc/boitier-fleet/db*.env` n'est lisible que par ce compte. Voir
[`tests/README.md`](tests/README.md) pour le détail.

## Redémarrage sécurisé

```bash
./run.sh
```

Vérifie le code (`py_compile`), lance la suite de tests, **interrompt le
redémarrage en cas d'échec** (reste sur la dernière version stable), sinon
recharge uniquement le process de cette app par `kill -HUP` — jamais
`service uwsgi <action> <app>` ni `systemctl <action> uwsgi <app>`, qui
redémarrent silencieusement *tout* uwsgi (vécu le 10 septembre 2026,
~28s de coupure totale sur toutes les apps, voir
`docs/operations/NOTES-evolutions.md`).

Le venv et le nom de l'app uwsgi ciblée sont déduits du nom du dossier
courant (`/opt/reports-dev` → `reports-dev` ; `/var/www/reports` →
`reports`), donc ces deux scripts sont utilisables tels quels dans les
deux environnements.

## Interface de dev

Une interface de dev permanente tourne à côté de la production, sur le
même principe qu'un canal dev/stable : voir
[`CAHIER-DES-CHARGES-REFONTE.md`](CAHIER-DES-CHARGES-REFONTE.md) §11.

- Code : `/opt/reports-dev` (ce dossier, dépôt Git local).
- Servie sur `https://docs.deltathermic.be/reports-dev/`, même
  authentification Google que la production.
- Base de données séparée (`dt_dev`, schéma et utilisateur MariaDB
  dédiés). Peuplée le 11 septembre 2026 par un dump complet de `dt`
  (décision explicite : même périmètre d'accès que la prod — même
  authentification Google, même liste blanche d'e-mails — donc pas
  d'exposition supplémentaire). `dt_dev` n'est **jamais** écrite en
  retour vers `dt` et diverge naturellement au fil des tests ; la
  resynchroniser au besoin par le même processus
  (`DROP`/`CREATE DATABASE dt_dev` + `mysqldump dt | mysql dt_dev`,
  voir `docs/operations/NOTES-evolutions.md`).
- Bandeau visuel orange « ENVIRONNEMENT DE DEV » sur chaque page pour ne
  jamais confondre avec la production.

## Gestion de la flotte

Le serveur de synchronisation est `docs.deltathermic.be` (VM fournie par
le service informatique). Documentation détaillée sur l'accès à ce
serveur et les précautions d'intervention : voir `OPERATIONS.md` dans le
dépôt `docs-infra` (versionne aussi la config nginx/uwsgi hors de ce
dépôt).
