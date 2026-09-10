# Cahier des charges — Refonte de `reports` sur le modèle `rpinode`

Statut : proposition, à valider avant tout début d'implémentation.
Portée : `reports` (API de flotte + UI web), servi par `docs.deltathermic.be`
via uWSGI (`/etc/uwsgi/apps-enabled/reports.ini`) et nginx
(`location /reports*` dans `/etc/nginx/sites-available/docs.deltathermic.be`).
Hors périmètre : `headscale-admin` (même logique applicable plus tard, non
traitée ici).

## 1. Contexte

`reports` a grossi par empilement de correctifs ponctuels depuis plusieurs
mois (deux fichiers monolithiques `api.py` — 1696 lignes — et `ui.py` — 1176
lignes —, une douzaine de fichiers `*.bak_<date>_<raison>` conservés à la
racine du dossier vivant, des scripts `test_bottle_*.py` de débogage jamais
transformés en suite de tests réelle, un `README.md` vide). Le journal
`NOTES-evolutions.md` documente plusieurs incidents directement liés à cette
absence de structure et de tests :

- **9 septembre** : `app.py` écrasé accidentellement par une copie de
  `headscale-admin/app.py` (pas de garde-fou, pas de test de bout en bout
  après restauration).
- **10 septembre (matin)** : coupure totale du service (~28 s) suite à un
  `service uwsgi restart reports` qui redémarre en réalité *tout* uwsgi.
- **10 septembre (matin, suite)** : `ui_app` non monté dans `app.py` pendant
  un jour entier après la reconstruction du 9 — jamais détecté faute de test
  fonctionnel, plus un 403 OAuth causé par le Service Worker de la PWA
  concurrençant le flux de connexion.

À l'inverse, `rpinode` (dépôt applicatif du boîtier `rpi01`) suit depuis sa
refonte une organisation modulaire documentée (`core` / `services` / `web`),
avec documentation de proximité, tests réels, et un script de redémarrage qui
n'autorise pas la mise en production d'un code cassé. L'objectif de ce
cahier des charges est de porter **les mêmes principes d'organisation** sur
`reports`, en tenant compte de ses contraintes propres (application serveur
WSGI de production, utilisateurs réels, authentification OAuth, PWA,
accès script en basic-auth).

## 2. Principes retenus du modèle `rpinode`

Ce qu'on porte tel quel :

1. **Séparation en trois couches** : `core` (infrastructure : configuration,
   accès données, chemins), `services` (logique métier par domaine),
   `web` (routage HTTP/HTML, aucune logique métier).
2. **Documentation de proximité** : un `README.md` racine qui explique
   vraiment l'architecture et comment travailler dessus, un `docs/` avec
   sous-dossiers `operations/` et `incidents/`, un `README.md` d'index dans
   chaque sous-package technique (`src/core/README.md`,
   `src/services/README.md`).
3. **`tools/` séparé du code applicatif** : migrations, scripts de débogage
   ponctuels, patches — jamais mélangés avec le code servi en production.
4. **Vraie suite de tests** (`tests/`) + script `run_tests.sh`, et un script
   de redémarrage (`run.sh` chez `rpinode`) qui **refuse de déployer** si les
   tests échouent.
5. **Discipline de sauvegarde par Git**, pas par fichiers `.bak_*` accumulés
   dans le dossier vivant.

Ce qu'on **n'importe pas tel quel**, avec justification :

- **Pas de réécriture du serveur HTTP à la main.** `rpinode` implémente son
  propre routeur sur `http.server` parce qu'il tourne seul, sans reverse
  proxy applicatif en face. `reports` tourne déjà derrière **Bottle**, un
  micro-framework conforme à la doctrine « pas de framework lourd » : le
  réécrire n'apporterait rien et introduirait un risque de régression élevé
  sur une application déjà en production avec des utilisateurs réels.
  → **On garde Bottle**, on ne change que l'organisation du code autour.
- **Pas de superviseur Rust « zéro coupure ».** Ce composant répond à un
  besoin propre à un boîtier embarqué qui redémarre fréquemment son process
  Python en pleine intervention terrain. `reports` est reconfiguré
  rarement et dispose déjà d'un mécanisme de rechargement sans coupure
  documenté (`kill -HUP` sur le PID de l'app dans `/run/uwsgi/app/reports/`,
  cf. règle de sécurité n°6 d'`OPERATIONS.md`). Pas de besoin identifié.
- **Pas de `data/` SQLite.** `reports` persiste dans MariaDB centrale (`dt`),
  ce n'est pas un boîtier isolé. L'équivalent pertinent est de centraliser
  la lecture de configuration/secrets (`/etc/boitier-fleet/db.env`) dans un
  module `core/config.py` unique, sur le modèle de `core/config.py` de
  `rpinode`, plutôt que de la logique ad hoc dans `db.py`.

## 3. État des lieux détaillé de `reports`

```
/var/www/reports/
├── app.py                    # 23 lignes — point d'entrée WSGI (mount api_app + ui_app)
├── api.py                    # 1696 lignes — TOUTES les routes /reports/api/*
├── ui.py                     # 1176 lignes — TOUTES les routes /reports/*  (+ une route /dev
│                              #   qui relit api.py/ui.py comme du texte pour lister les routes)
├── db.py                     # connexion MariaDB + lecture manuelle de /etc/boitier-fleet/db.env
├── mqtt_publisher.py          # service séparé (reports-mqtt-publisher.service), statut non
│                              #   tranché (cf. décision en attente #1 d'OPERATIONS.md)
├── sql_script.py / .sql, schema_update.sql   # scripts de migration/maintenance à la racine
├── views/*.tpl                # 10 templates Bottle (SimpleTemplate)
├── static/                    # JS/CSS/icônes/manifest/service worker
├── webdav/                    # point de montage nginx pour scanz/pdfsync (basic auth), vide,
│                              #   sans rapport avec le code Python
├── README.md                  # vide (une ligne sans rapport)
├── NOTES-evolutions.md         # journal d'incidents à jour et de bonne qualité — à conserver
├── HEADSCALE-ACL.md            # doc historique — à conserver
├── 8 fichiers api.py.bak_* / app.py.bak_*         # aucune trace dans Git
├── 7 fichiers test_bottle_*.py, test_db.py, test_mount.py, test_server.py,
│   test_sync.py, test_uwsgi.py, test_api_mqtt.py   # scripts de débogage ponctuels,
│                              #   pas une suite de tests exécutable en CI/avant déploiement
└── __pycache__/
```

Constats :

- **Aucun dépôt Git** sur `/var/www/reports` lui-même (seule `docs-infra` en
  conserve une copie synchronisée manuellement).
- **`api.py` mélange au moins 7 domaines métier distincts** dans un seul
  fichier : usage/ping, register (+ auto), sync, chantiers/antennes,
  trends/points-config, logs, headscale (enroll + routes), maintenance des
  templates, gestion des colonnes. Même chose pour `ui.py` (accueil,
  chantier, nodes, SQL debug, maintenance templates, SSE).
- **18 routes UI + 15 routes API**, aucune couverte par un test automatisé
  rejouable.
- Le `README.md` ne documente rien : un développeur qui arrive doit lire
  1696 + 1176 lignes pour comprendre le système.

## 4. Objectifs de la refonte

1. Éclater `api.py` et `ui.py` en modules `services/*.py` (logique métier,
   sans dépendance à Bottle) + modules `web/*.py` (routage Bottle uniquement,
   délègue tout de suite à `services/`).
2. Centraliser configuration/secrets dans `core/config.py`, la connexion DB
   dans `core/database.py`.
3. Fournir une vraie suite de tests (`tests/`, exécutable via
   `run_tests.sh`), couvrant au minimum : montage WSGI complet (régression
   de l'incident du 10 septembre), les routes critiques (`/register`,
   `/sync`, `/ping`), le rendu des templates, la config OAuth/exemptions
   PWA (`sw.js`, `manifest.json` accessibles sans authentification).
4. Fournir un script de redémarrage sûr (`run.sh`) : tests d'abord, puis
   rechargement **ciblé** de l'app (`kill -HUP <pid>` lu dans
   `/run/uwsgi/app/reports/pid`), jamais `service uwsgi restart`.
5. Réécrire `README.md` (vue d'ensemble réelle, architecture, comment lancer
   les tests, comment déployer) et ajouter un `docs/README.md` d'index,
   en déplaçant `NOTES-evolutions.md` et `HEADSCALE-ACL.md` sous
   `docs/operations/` ou `docs/incidents/` selon leur nature.
6. Ranger les scripts de migration (`sql_script.*`, `schema_update.sql`)
   sous `tools/migrations/`, les scripts de diagnostic ponctuels utiles sous
   `tools/debug/` ; supprimer les scripts `test_bottle_*.py` devenus obsolètes
   une fois leur contenu utile récupéré dans la vraie suite de tests.
7. Mettre `reports` sous Git (dépôt dédié ou intégration réfléchie avec
   `docs-infra` — à trancher, voir §8) pour remplacer la discipline des
   fichiers `.bak_*` par un historique réel.
8. **Ne rien changer aux contrats externes** : URLs (`/reports`,
   `/reports/api/*`, `/reports/sw.js`, `/reports/manifest.json`,
   `/reports/reports_sse`, `/reports/chantier/<id>/reports_sse`), noms des
   fichiers imposés par la configuration système (`app.py` reste le module
   `app:application` attendu par `reports.ini`), comportement fonctionnel
   des routes.

## 5. Non-objectifs (hors périmètre explicite)

- Changer de framework web (Bottle reste).
- Changer la base de données ou son schéma.
- Modifier la configuration nginx/oauth2-proxy (sauf si un chemin de fichier
  interne changeait de façon à casser une règle `location =` existante —
  auquel cas la config nginx devra être mise à jour en même temps, avec
  sauvegarde horodatée et `nginx -t` avant reload, comme l'exige
  `OPERATIONS.md`).
- Trancher le statut de `mqtt_publisher.py` (décision en attente #1) ou le
  rôle repris de `/bottle`/`/bottledev` (décision en attente #5) : ces deux
  points sont **pré-requis à discuter avec Marc**, pas résolus par ce
  cahier des charges (voir §8).

## 6. Architecture cible proposée

**Etat au 10 septembre 2026 (nuit)** : `core/`, l'éclatement d'`api.py`
et l'éclatement d'`ui.py` sont faits dans `/opt/reports-dev` (voir
NOTES-evolutions.md). Nuance par rapport au tableau ci-dessous : les
fichiers `services/*.py` et `web/*.py` contiennent encore le routage
Bottle (decorateurs `@api_app.get`/`post`, `@ui_app.get`/`post`)
directement, pas seulement de la logique pure - voir la nuance assumee
au §9. `web/api.py` et `web/ui.py` existent deja mais sous une forme
d'assemblage (routes transverses + import des modules `services/`/`web/`
pour effet de bord), pas encore le pur routeur qui delegue decrit ici.
Contrairement au tableau ci-dessous, la majorite des pages reste dans
`web/ui.py` : seuls `web/stream.py` (SSE) et
`services/templates_maintenance.py` ont ete extraits, les autres routes
restant trop couplees entre elles pour un decoupage plus fin sans filet
de tests (memes raisons qu'au §9).

```
reports/
├── app.py                     # inchangé dans son rôle : mount api_app + ui_app,
│                               #   reste le fichier attendu par reports.ini
├── src/
│   ├── core/
│   │   ├── config.py           # lecture centralisée de /etc/boitier-fleet/db.env
│   │   │                        #   (et de tout futur secret), remplace la logique
│   │   │                        #   actuellement dans db.py
│   │   ├── database.py         # get_db() — inchangé fonctionnellement, déplacé
│   │   └── paths.py            # chemins absolus (views/, static/, webdav/)
│   ├── services/                # logique métier, sans import Bottle
│   │   ├── fleet.py              # register, register/auto, ping, usage
│   │   ├── sync.py               # /sync (remontée batch des boîtiers)
│   │   ├── chantiers.py          # chantiers, antennes, net_profiles, rename
│   │   ├── trends.py             # trends, points-config, table/column/delete
│   │   ├── logs.py               # logs (GET/POST)
│   │   ├── headscale.py          # headscale/enroll, headscale/routes
│   │   ├── templates_maintenance.py   # maintenance/templates/*
│   │   └── mqtt_publisher.py     # statut à trancher (voir §8) avant de le rapatrier ici
│   └── web/
│       ├── api.py                # api_app Bottle — routage uniquement, délègue à services/
│       ├── ui.py                 # ui_app Bottle — routage + rendu de templates
│       ├── stream.py             # extrait les 2 routes SSE (reports_sse), sur le modèle
│       │                        #   de web/stream.py chez rpinode
│       └── templating.py         # wrapper léger autour de bottle.template si utile
│                                 #   (sinon, garder l'appel direct à bottle.template)
├── templates/                    # renommage de views/ pour cohérence de vocabulaire
│   └── *.tpl                     # inchangés
├── static/                       # inchangé
├── webdav/                       # inchangé (point de montage nginx, sans code Python)
├── tests/
│   ├── test_wsgi_mount.py         # non-régression directe de l'incident du 10/09 :
│   │                              #   vérifie que app.application expose bien /reports
│   │                              #   ET /reports/api
│   ├── test_fleet.py, test_sync.py, test_chantiers.py, ...  # un fichier par service
│   └── test_pwa_exemptions.py     # sw.js / manifest.json accessibles sans session
├── tools/
│   ├── migrations/                # sql_script.py, sql_script.sql, schema_update.sql
│   └── debug/                     # scripts de diagnostic ponctuels conservés utiles
├── docs/
│   ├── README.md                  # index
│   ├── operations/
│   │   └── NOTES-evolutions.md    # déplacé tel quel
│   └── incidents/
│       └── HEADSCALE-ACL.md       # déplacé tel quel (ou reclassé si mieux nommé)
├── run_tests.sh
├── run.sh                         # tests puis kill -HUP ciblé (jamais service uwsgi ...)
└── README.md                      # réécrit : vue d'ensemble, architecture, tests, déploiement
```

### Table de correspondance ancien → nouveau

| Actuel | Nouveau | Remarque |
|---|---|---|
| `api.py` (1696 l.) | `src/web/api.py` + `src/services/{fleet,sync,chantiers,trends,logs,headscale,templates_maintenance}.py` | découpage par domaine |
| `ui.py` (1176 l.) | `src/web/ui.py` + `src/web/stream.py` | SSE extrait, reste routage + rendu |
| `db.py` | `src/core/config.py` + `src/core/database.py` | séparation lecture config / connexion |
| `mqtt_publisher.py` | `src/services/mqtt_publisher.py` **ou suppression** | dépend de la décision en attente #1 |
| `sql_script.py`, `sql_script.sql`, `schema_update.sql` | `tools/migrations/` | |
| `test_bottle_*.py`, `test_db.py`, `test_mount.py`, `test_server.py`, `test_sync.py`, `test_uwsgi.py`, `test_api_mqtt.py` | `tests/*.py` (réécrits en tests réels) ou supprimés | contenu utile récupéré, scripts scratch abandonnés |
| `views/*.tpl` | `templates/*.tpl` | renommage seul |
| `*.bak_*` épars (api.py, app.py, NOTES-evolutions.md) | supprimés du dossier vivant | remplacés par l'historique Git |
| `README.md` (vide) | réécrit | modèle : `README.md` de `rpinode` |
| `NOTES-evolutions.md` | `docs/operations/NOTES-evolutions.md` | contenu conservé tel quel |
| `HEADSCALE-ACL.md` | `docs/incidents/HEADSCALE-ACL.md` | contenu conservé tel quel |

## 7. Méthode de migration (aucun risque pour la production avant bascule)

1. **Copie de travail** (déjà proposée par vous) : dupliquer
   `/var/www/reports` vers un emplacement **hors `/var/www`**, à savoir
   `/opt/reports-dev/` (voir §11 : ce dossier ne reste pas une copie de
   travail jetable, il devient l'interface de dev permanente, servie par
   sa propre app uwsgi), pour exclure tout risque qu'nginx serve
   accidentellement un fichier de la copie de travail (aucune règle
   `location` ne pointe vers `/opt`, contrairement à un sous-dossier de
   `/var/www`).
2. Initialiser un dépôt Git dans cette copie de travail dès le départ, pour
   obtenir un historique de la refonte elle-même.
3. Réorganiser progressivement dans cette copie, module par module, en
   gardant à chaque étape un `app.py` qui fonctionne et des tests qui
   passent (`./run_tests.sh` vert avant chaque commit).
4. **Valider en local** : rejouer les tests, vérifier avec
   `python3 -m py_compile` sur tous les fichiers, et si possible exécuter
   l'app dans le venv `/opt/venv/reports` pointé sur cette copie pour un
   test fonctionnel réel (montage WSGI complet, comme l'exige la leçon de
   l'incident du 10 septembre).
5. **Bascule** : une fois la copie validée,
   - sauvegarde horodatée de `/var/www/reports` actuel
     (`cp -a /var/www/reports /var/backups/docs-app/reports-preref-$(date +%Y%m%d_%H%M%S)`),
   - synchronisation du contenu validé vers `/var/www/reports`,
   - `python3 -m py_compile` sur les fichiers déployés,
   - rechargement ciblé : `kill -HUP $(cat /run/uwsgi/app/reports/pid)`
     (jamais `service uwsgi restart`/`systemctl restart uwsgi`),
   - test de bout en bout en navigateur réel (pas seulement `curl`), y
     compris avec une PWA déjà installée, conformément à la leçon du 10
     septembre.
6. **Rollback** : si un problème apparaît après bascule, restaurer
   immédiatement la sauvegarde horodatée de l'étape 5 et recharger via le
   même `kill -HUP`.
7. **Après validation en production** : mettre à jour
   `docs-infra/var/www/reports/` (copie + `git commit` + `git push`) et
   `OPERATIONS.md` (la refonte devient un fait acquis, à décrire dans la
   section « État »).

## 8. Décisions à trancher avant/pendant (avec Marc)

1. **Dépôt Git de `reports`** : dépôt dédié (comme `rpinode`) ou intégré
   différemment à `docs-infra` ? `docs-infra` mirrors actuellement
   `/var/www/reports` par simple copie (`cp` + commit manuel) — une fois
   `reports` versionné nativement, faut-il arrêter ce mirroring redondant
   dans `docs-infra` et n'y garder que la config système (nginx, uwsgi.ini) ?
2. **Statut de `mqtt_publisher.py`** (décision en attente #1
   d'`OPERATIONS.md`) : prototype à finaliser, à intégrer dans
   `services/`, ou à retirer ? Impacte directement où (et si) ce fichier
   apparaît dans l'arborescence cible.
3. **Rôle repris de `/bottle`/`/bottledev`** (décision en attente #5) :
   si ces rôles doivent être repris sous `reports`, autant les intégrer
   directement dans la nouvelle organisation (`services/` dédié) plutôt que
   de les rajouter après coup.
4. **Renommage `views/` → `templates/`** : purement cosmétique, sans risque,
   mais à valider (aucun gain fonctionnel, juste cohérence de vocabulaire
   avec `rpinode`).

## 9. Critères d'acceptation

- [x] `api.py` (1696 lignes) est éclaté par domaine metier dans
      `services/*.py` (fleet, chantiers, sync, trends, logs, headscale),
      `web/api.py` ne gardant que l'assemblage et les routes transverses
      (10 septembre 2026). **Nuance assumée** : chaque route garde sa
      logique metier et ses requetes SQL inline (ouverture DB,
      `request.json`, `json_ok`/`json_error`) - la separation complete
      « services sans aucune dependance Bottle / web qui ne fait que
      router » est **délibérément reportée** tant qu'il n'existe pas de
      suite de tests pour rattraper une regression subtile lors d'une
      reecriture aussi profonde (voir NOTES-evolutions.md, entree du 10
      septembre soir, pour la justification complete). A reprendre une
      fois le point suivant (tests reels) atteint.
- [x] `ui.py` (1169 lignes) est éclaté en `web/ui.py` (l'essentiel des
      pages), `web/stream.py` (SSE) et `services/templates_maintenance.py`
      (10 septembre 2026, nuit). **Même nuance assumée** que pour `api.py` :
      routage et logique restent ensemble par route. Bug réel trouvé et
      corrigé au passage : le bandeau visuel de dev (§11) ne s'affichait
      jamais (`bottle.request.path` non fiable à travers un montage Bottle,
      voir NOTES-evolutions.md).
- [x] `./run_tests.sh` exécute une suite réelle (11 septembre 2026, 32
      tests) et couvre : montage WSGI (`/reports-dev` et `/reports-dev/api`
      répondent, garde-fou sur le nombre de routes), une route par service,
      l'exemption PWA de `sw.js`/`manifest.json`, et le bug de chemins en
      dur du 10 septembre (`test_core_paths.py`). Déduit le venv/l'app du
      nom du dossier courant, donc réutilisable tel quel après promotion
      en production.
- [x] `./run.sh` refuse de recharger l'app si les tests échouent (vérifié
      manuellement avec un échec provoqué), et ne recharge jamais que le
      process de cette app (jamais `service uwsgi ...`).
- [ ] Plus aucun fichier `*.bak_*` dans le dossier applicatif vivant :
      l'historique est dans Git.
- [ ] `README.md` permet à quelqu'un qui découvre le projet de comprendre
      l'architecture, lancer les tests et déployer, sans lire le code.
- [ ] Toutes les URLs externes existantes répondent à l'identique
      (vérifié en navigateur réel, session OAuth incluse, PWA installée
      incluse).
- [ ] `docs-infra` et `OPERATIONS.md` mis à jour après bascule en
      production.

## 10. Risques identifiés

| Risque | Mitigation |
|---|---|
| Régression silencieuse sur une route peu utilisée | Suite de tests couvrant les 33 routes existantes avant bascule |
| Casse d'une règle nginx `location =` si un chemin change | Aucun changement de chemin externe prévu (§4 point 8) ; si nécessaire, appliquer la règle de sécurité n°2 d'`OPERATIONS.md` (backup horodaté + `nginx -t` avant reload) |
| Coupure de service pendant la bascule | Rechargement ciblé `kill -HUP`, jamais `service uwsgi restart` (règle de sécurité n°6) |
| Conflit avec le mirroring `docs-infra` existant | Décision à trancher en §8.1 avant de committer quoi que ce soit côté `docs-infra` |
| PWA/Service Worker cassant le flux OAuth | Test de bout en bout en navigateur réel avec PWA déjà installée, comme prescrit par la leçon du 10 septembre |

## 11. Interface de dev à côté de l'interface stable

`reports` est en tout début de développement : il est utile d'avoir en
permanence une interface de dev accessible en navigateur, à côté de
l'interface stable, plutôt que de tester uniquement en local avant
bascule. La copie de travail du §7 devient donc l'environnement de dev
permanent (`/opt/reports-dev/`), servi par sa propre app uwsgi — et non un
répertoire jetable supprimé après la refonte.

### Principe

Deux instances **uwsgi indépendantes** du même code, sur deux chemins
nginx distincts (`/reports` et `/reports-dev`), derrière la même
authentification Google, mais avec **base de données et venv séparés**
pour qu'un test cassé en dev ne touche jamais les vraies données de
flotte remontées par les boîtiers.

```mermaid
flowchart TD
    Browser[Navigateur] -->|443 TLS| Nginx[nginx]
    Nginx -->|auth_request identique| OAuth[oauth2-proxy-google]
    Nginx -->|/reports vers socket prod| Prod[uwsgi app reports]
    Nginx -->|/reports-dev vers socket dev| Dev[uwsgi app reports-dev]
    Prod --> DBProd[MariaDB schema dt]
    Dev --> DBDev[MariaDB schema dt_dev]
    Prod -.chdir.-> DirProd[/var/www/reports]
    Dev -.chdir.-> DirDev[/opt/reports-dev checkout Git]
```

### Détail par composant

1. **Code — un préfixe configurable.** `app.py` (dev uniquement) lit
   `REPORTS_BASE_PATH` (défaut `/reports`, donc la prod n'a besoin
   d'aucune modification) et mount `api_app`/`ui_app` dessus :
   ```python
   BASE_PATH = os.environ.get("REPORTS_BASE_PATH", "/reports")
   application.mount(f"{BASE_PATH}/api", api_app)
   application.mount(BASE_PATH, ui_app)
   ```
2. **Deux fichiers uwsgi, jamais mélangés** :
   `/etc/uwsgi/apps-enabled/reports-dev.ini`, socket
   `/tmp/uwsgi.reports-dev.socket`, `virtualenv = /opt/venv/reports-dev`
   (venv séparé du venv de prod), `chdir = /opt/reports-dev`,
   `env = REPORTS_BASE_PATH=/reports-dev`,
   `env = DB_ENV_FILE=/etc/boitier-fleet/db-dev.env`. `reports.ini` (prod)
   reste inchangé. Chaque app a son propre PID sous `/run/uwsgi/app/<app>/pid`,
   rechargeable indépendamment par `kill -HUP` (règle de sécurité n°6).
3. **Base de données séparée — point le plus important.** Schéma MariaDB
   dédié `dt_dev` (même serveur), utilisateur MariaDB dédié à droits
   restreints, `/etc/boitier-fleet/db-dev.env` pointant dessus.
   `core/database.py` lit `DB_ENV_FILE` depuis l'environnement plutôt
   qu'en dur. Aucun boîtier réel ne doit jamais pointer vers
   `/reports-dev/api` (les `FleetClient` de la flotte utilisent
   `/reports/api` en dur — à vérifier une fois, puis documenter).
4. **nginx — bloc symétrique, même OAuth.** `location /reports-dev`,
   `location = /reports-dev/sw.js` et `.../manifest.json` (exemptées de
   `auth_request`, même leçon que l'incident PWA du 10 septembre), et la
   route SSE `location ~ ^/reports-dev/reports_sse$`, toutes pointées vers
   `unix:/tmp/uwsgi.reports-dev.socket` et protégées par le même
   `auth_request /oauth2-google/auth` que la prod (même liste blanche
   d'e-mails). Le scope du Service Worker étant basé sur le chemin, une
   PWA installée sur `/reports-dev/` ne peut pas entrer en conflit avec
   celle installée sur `/reports/`.
5. **Garde-fou visuel.** Bandeau dans `layout.tpl`, conditionné à
   `REPORTS_BASE_PATH != "/reports"` (« ENVIRONNEMENT DE DEV — données non
   réelles »), pour ne jamais confondre les deux environnements à l'œil.

### Workflow quotidien

1. Édition dans `/opt/reports-dev` (checkout Git).
2. `./run_tests.sh` puis `kill -HUP $(cat /run/uwsgi/app/reports-dev/pid)`
   — rien touché côté prod.
3. Vérification fonctionnelle sur `https://docs.deltathermic.be/reports-dev`.
4. Une fois satisfait : promotion vers la prod en suivant la procédure de
   bascule du §7 (backup horodaté, copie, `py_compile`, `kill -HUP` sur
   `reports` cette fois, jamais sur `reports-dev`).

### Leçon tirée de l'ancien `/bottle`/`/bottledev`

Cet ancien couple app de démo/config nginx a fini archivé le 10 septembre
faute d'usage réel et de documentation — exactement le sort à éviter ici :

- Nommage sans ambiguïté (`reports-dev`, pas de nom générique type « démo »).
- Documenté dans le `README.md` de `reports` **et** dans `OPERATIONS.md`
  dès sa création.
- Si `reports-dev` devient inutilisé après la fin de la refonte active, il
  faudra l'archiver comme `/bottle` l'a été plutôt que de le laisser mourir
  en silence.

---

*Document à valider avant toute implémentation. Une fois approuvé, la copie
de travail sera créée sous `/opt/reports-dev/` et le travail de
restructuration démarrera module par module, en commençant par
`core/config.py` et `core/database.py` (fondations sans dépendance
descendante).*
