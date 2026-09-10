# Notes & Évolutions (Reports API)

## Évolutions récentes (Septembre 2026)

- [x] **Purger les relevés d'un chantier ou d'un équipement / device** :
  - **Fonctionnalité** : Possibilité de purger tous les relevés (`boitier_trends`) d'un chantier complet (bouton en en-tête avec confirmation de sécurité par saisie du mot "PURGER") ou de purger unitairement les relevés d'un équipement/device particulier (bouton poubelle 🗑️ par ligne ou via le filtre des devices).
  - **Backend** : Ajout de la route `POST /reports/chantier/<id>/purge` dans `ui.py` avec filtrage possible par `device`, `protocol` et `boitier_id`.
  - **Frontend** : Intégration dans `views/chantier.tpl`, `views/points_table.tpl` et `views/points_scripts.tpl` avec gestion sécurisée des identifiants (attributs data).

- [x] **Remplacement du short-polling par du Server-Sent Events (SSE) pour les graphiques** :
  - **Problème** : Les vues contenant un graphique (`chantier.tpl` et la vue mobile `chart_view.tpl`) rafraîchissaient leurs données en envoyant une requête POST complète toutes les 5 secondes (`setInterval`). En plus d'inonder le réseau, cela saturait le pool de uWSGI et polluait la console du navigateur.
  - **Code (Backend & Frontend)** : 
    - Ajout d'une nouvelle route `GET /chantier/<id>/reports_sse` (`ui.py`) renvoyant un flux `text/event-stream`. La route boucle côté serveur et notifie le client (`yield "data: update\n\n"`) *uniquement* lorsque le `MAX(timestamp)` du chantier dans `boitier_trends` évolue.
    - Côté JS, l'interrogation par `setInterval` a été remplacée par un abonnement `EventSource` pointant vers cette nouvelle route. Les données volumineuses du graphique (`fetchChartData`) ne sont désormais téléchargées que lorsqu'un changement réel est signalé par le serveur.
  - **Infrastructure (Nginx & uWSGI)** : 
    - **Nginx** bloquant par défaut le flux SSE en attendant la fin de la réponse uWSGI, ajout d'un bloc `location ~ ^/reports/chantier/[0-9]+/reports_sse$` dans `docs.deltathermic.be` avec l'instruction vitale `uwsgi_buffering off;`.
    - **uWSGI** fonctionnant initialement en mode mono-thread (un flux SSE long aurait bloqué l'unique worker et gelé tout le site), ajout de `enable-threads = true` et `threads = 10` dans `reports.ini` pour assurer la gestion simultanée des clients.

## À venir

- [ ] **Authentification** : Remplacer / intégrer l'authentification actuelle de l'interface par une identification Azure AD avec Microsoft Authenticator de la société (mécanisme en attente d'implémentation).

## Bugs connus / en cours d'investigation

- [x] **BUG RESOLU (confirme par la console du navigateur, 19/08) : `/reports/chantier/<id>/chart-data` renvoyait une erreur 500** quand au moins un des points selectionnes (typiquement via le bouton "Tous") n'avait encore aucun releve dans `boitier_trends`. Cause : `pymysql` renvoie un **tuple vide `()`** (au lieu d'une liste) quand une requete ne retourne aucune ligne, et `tuple.reverse()` n'existe pas -> `AttributeError`, jamais catch, remontait en 500. Corrige dans `ui.py` (`chantier_chart_data`) par `rows = list(cur.fetchall())` avant `.reverse()`. Reproduit et valide par un test direct (payload avec un point a 0 ligne) avant et apres le correctif.
  - Cette boucle d'erreurs 500 toutes les 5 secondes (rafraichissement automatique du graphique) polluait fortement la console et rendait le diagnostic du bug QR code (ci-dessous) tres difficile a isoler. A verifier en priorite au prochain signalement : le bouton QR code fonctionne peut-etre deja correctement a present (la console ne montrait aucune exception provenant de `toggleQRCode` lors du dernier test, uniquement les 500 de `chart-data`).

- [ ] **QR Code du graphique (page `/reports/chantier/<id>`) : le bouton "QR Code (Mobile)" fermait le panneau mais ne le rouvrait pas.**
  - 5eme tentative (en place actuellement) : `toggleQRCode()` a ete rendue defensive - le panneau est desormais **toujours** affiche (`display:flex`) des l'ouverture demandee, la generation du QR (et ses eventuelles erreurs) se faisant APRES cette bascule d'affichage. Toute exception lors de la generation est desormais capturee ET affichee **directement dans le panneau** (nouveau `<p id="qr-code-error">`), au lieu d'etre seulement loggee dans la console. Un message specifique s'affiche aussi si `selectedPoints` est vide. Cycle ouvrir/fermer/rouvrir valide par harnais de test Node.js (3 clics successifs, aucune exception, bascule d'affichage confirmee "flex"/"none"/"flex").
  - **CAUSE RACINE IDENTIFIEE ET CORRIGEE (19/08)** : confirmee par l'utilisateur en supprimant temporairement le `<canvas id="trendChart">` -> le bouton fonctionnait alors normalement. Il ne s'agissait donc PAS d'un bug JavaScript mais d'un piege CSS Flexbox classique : le conteneur du graphique (`flex-grow:1`) n'avait pas `min-width:0`, donc le `<canvas>` (dimensionne par Chart.js) refusait de se reduire et debordait visuellement PAR-DESSUS le panneau QR (siblings flex, `min-width:auto` par defaut empeche le retrecissement en presence de contenu large). Corrige dans `views/chantier.tpl` :
    - ajout de `min-width: 0` sur le conteneur flex du graphique ;
    - ajout de `flex-shrink: 0`, `position: relative` et `z-index: 5` sur `#qr-code-container` (defense en profondeur) ;
    - appel explicite a `chartInstance.resize()` a chaque bascule du panneau QR (ouverture ET fermeture), pour forcer Chart.js a recalculer immediatement la taille du canevas sans attendre son detecteur de redimensionnement automatique.
  - Statut : corrige, a reconfirmer par l'utilisateur au prochain test.
  - Symptôme rapporté par l'utilisateur : un clic sur le bouton ne produit aucun changement visible. Testé sur le poste de l'utilisateur (navigateur non précisé).
  - Historique des tentatives (toutes déployées, aucune n'a résolu le problème côté utilisateur) :
    1. 1ere implementation : appel a un service externe `api.qrserver.com` pour generer l'image -> suspecte d'etre bloque par un pare-feu/DNS filtrant/ad-blocker. Remplace par une generation 100% locale (bibliotheque `qrcode.min.js`, licence MIT, basee sur le travail de Kazuhiko Arase, stockee dans `static/`).
    2. 2eme tentative : dessin direct sur un `<canvas>` visible dans la modale, avec `qrContainer.style.display = 'flex'` place APRES le dessin -> hypothese : un canevas dessine pendant qu'il est `display:none` ne se "peint" pas toujours (corrige en observant qu'une fermeture/reouverture de la fenetre faisait apparaitre le QR).
    3. 3eme tentative : afficher le conteneur en premier, puis dessiner via `requestAnimationFrame()` (pour laisser le temps au navigateur de recalculer la mise en page avant de dessiner) -> toujours signale comme non fonctionnel.
    4. 4eme tentative (en place actuellement) : le QR est desormais dessine sur un `<canvas>` cree en memoire via `document.createElement('canvas')`, JAMAIS insere dans le DOM (donc jamais soumis a un etat `display:none`), puis exporte en image via `canvas.toDataURL('image/png')` et assigne au `src` d'une balise `<img>` classique. Cette approche a ete validee par un harnais de test Node.js simulant l'execution sequentielle des balises `<script>` d'un navigateur (aucune exception, bascule d'affichage confirmee) -> **toujours signale comme non fonctionnel par l'utilisateur**, malgre les tests reussis en simulation.
  - Pistes non encore explorees (a tester en priorite au prochain passage, idealement avec acces reel aux outils de developpement du navigateur de l'utilisateur - Chrome DevTools / Safari Web Inspector - pour lire la console) :
    - Verifier s'il y a une **erreur JavaScript silencieuse plus tot dans le chargement de la page** qui empecherait `toggleQRCode` d'etre correctement attache (ex: un point-virgule ou une accolade manquante ailleurs dans `chantier.tpl`, ou un conflit de nom de variable).
    - Verifier le **cache du navigateur / Service Worker** : bien que `sw.js` ne fasse actuellement aucun `caches.put()` (donc ne devrait rien mettre en cache), demander explicitement a l'utilisateur de faire un **hard refresh** (Ctrl+Maj+R) ou de vider le cache du site avant de re-tester, pour ecarter une version obsolete de `chantier.tpl` ou `qrcode.min.js` servie depuis le cache HTTP disque du navigateur.
    - Demander a l'utilisateur le **navigateur et l'appareil precis** utilises (Chrome/Firefox/Safari, desktop/mobile) pour reproduire dans un environnement equivalent.
    - Demander a l'utilisateur d'**ouvrir la console JavaScript** (F12) au moment du clic et de rapporter le message d'erreur exact, le cas echeant.
    - Envisager de remplacer le bouton par un `<a>` avec un `href` direct vers l'URL du graphique (sans QR code du tout) en solution de repli si le probleme persiste, le temps de diagnostiquer plus finement.

## 9 septembre 2026 (après-midi) — taggage auto `tag:fleet` + incident app.py

### Ajout : `_ensure_fleet_tag()`

`POST /headscale/routes` pose désormais automatiquement `tag:fleet` sur le
nœud du boîtier appelant s'il ne l'a pas déjà (idempotent, non bloquant en
cas d'échec). Constante `HEADSCALE_FLEET_TAG = "tag:fleet"` ajoutée à côté
de `HEADSCALE_BIN`/`HEADSCALE_USER_ID`. `API_VERSION` -> `1.2.1`.
Détail côté dépôt `rpinode` : `docs/integrations/HEADSCALE_AUTO_ENROLL.md`.

### Incident (auto-infligé) : `/var/www/reports/app.py` écrasé

En préparant ce changement, `systemctl reload uwsgi` a révélé que
`/var/www/reports/app.py` était devenu une **copie exacte de
`/var/www/headscale-admin/app.py`** (même contenu, `app = Bottle()` avec les
routes `/headscale-admin/*`, aucune trace de `application` ni d'import de
`api.py`). Origine exacte non déterminée avec certitude (mtime 09/09 11:03,
probablement une copie accidentelle pendant les manipulations de l'incident
SSH du matin même) : cassait le chargement uWSGI dès qu'un reload forçait une
relecture depuis le disque (les workers déjà en mémoire avant ça continuaient
à fonctionner avec l'ancien code, masquant le problème).

Le vrai `app.py` (le point d'entrée WSGI de `reports`, absent de tout backup
sur le serveur) a été reconstruit à l'identique de ce qu'imposent
`api.py` (qui expose `api_app = Bottle()` sans aucun préfixe dans ses routes,
ex: `@api_app.get("/usage")`) et nginx (qui ne tronque PAS le préfixe
`/reports/api`, contrairement à une hypothèse initiale) :

```python
from bottle import Bottle
from api import api_app

application = Bottle()
application.mount('/reports/api', api_app)
```

Ancien fichier fautif conservé : `app.py.bak_20260909_wrongcopy_headscale_admin`.

**Leçon** : `/var/www/reports/app.py` n'a **aucune sauvegarde fiable** sur ce
serveur en dehors de ce dépôt de notes. À versionner ou sauvegarder
explicitement si retouché, ce fichier ne fait que 5 lignes mais est le seul
point de couture entre `api.py` et uWSGI.

## 10 septembre 2026 (matin) — coupure de service lors de l'archivage de `bottle`/`bottledev`

### Contexte

Décision de retirer `/bottle` (uwsgi `bottledemo.socket`, app de démo) et
`/bottledev` (reverse proxy vers `127.0.0.1:8081`, plus rien n'écoutait
dessus) : leurs rôles seront repris sous `reports`. Avant suppression,
archive complète créée sur `docs` dans
`/var/backups/docs-app/archive-bottle-20260910/` (`600`/`700`,
`root:root`) : `var-www-bottle.tar.gz`, `var-www-bottledev.tar.gz`,
`bottle.ini`, `bottledev.ini`.

### Incident (auto-infligé) : `service uwsgi stop bottle` a arrêté tout uwsgi

Pour arrêter uniquement l'app `bottle`, la commande
`sudo service uwsgi stop bottle` a été utilisée en pensant cibler
l'instance nommée `bottle` (syntaxe documentée par le script
`/etc/init.d/uwsgi` : `service uwsgi <commande> <confname>`). En réalité,
sous ce système, `service <nom> <action> <arguments-supplementaires>`
passe par systemd (`systemd-sysv-generator`) qui **ignore silencieusement
les arguments après l'action** et traduit l'appel en
`systemctl stop uwsgi` pur et simple : **tout le service a été arrêté**,
donc `reports` et `headscale-admin` avec.

Détecté immédiatement (`systemctl status uwsgi` → `inactive (dead)`),
corrigé par `sudo systemctl start uwsgi`. **Coupure totale d'environ
28 secondes** (10:32:24 → 10:32:52 UTC). Vérifié après coup :
`reports` (redirection Azure AD, HTTP 302) et `headscale-admin`
(basic auth, HTTP 401) répondaient normalement, sockets `uwsgi`
recréés sous `/run/uwsgi/app/*`.

**Leçon : ne jamais utiliser `service uwsgi <action> <app>` (ni
`systemctl <action> uwsgi <app>`) sur ce serveur pour cibler une
app individuelle — cela arrête tout le service.** Pour arrêter une
app précise sans toucher aux autres : lire son PID dans
`/run/uwsgi/app/<app>/pid` et l'arrêter directement. Attention
également au signal : uWSGI traite **`SIGTERM` par défaut comme un
ordre de rechargement des workers** (ils redémarrent aussitôt), pas
comme un arrêt — il faut envoyer `SIGINT` (ou `SIGQUIT` pour un arrêt
brutal) au PID du master pour obtenir un arrêt réel.

Séquence qui a fonctionné, sans impact sur les autres apps (même
cgroup `uwsgi.service`, mais processus indépendants) :

```sh
sudo kill -INT $(sudo cat /run/uwsgi/app/bottle/pid)
sudo rm /etc/uwsgi/apps-enabled/bottle.ini
sudo rm /etc/uwsgi/apps-available/bottle.ini /etc/uwsgi/apps-available/bottledev.ini
```

Les blocs `location /bottle` et `location /bottledev` ont ensuite été
retirés de `/etc/nginx/sites-available/docs.deltathermic.be` (copie
horodatée préalable, `nginx -t` avant `systemctl reload nginx` —
`reload`, pas `restart`, sans coupure cette fois). Changement répercuté
dans le dépôt `mfache/docs-infra` (commit `b175195`).

## 10 septembre 2026 (matin, suite) — identification unifiée via Google

### Contexte

L'usage d'Azure AD (Entra ID) chez Deltathermic n'est toujours pas tranché.
En attendant, `/reports` (UI + SSE) et `/headscale-admin` sont unifiés sous
une identification par **compte Google**, le seul utilisateur actuel étant
Marc (`marc@fache.be`).

### Architecture : deux instances `oauth2-proxy` en parallèle

- **Existante (Azure/Entra ID)**, inchangée : `127.0.0.1:4180`,
  `/etc/oauth2-proxy/oauth2-proxy.cfg`, préfixe `/oauth2/`. Ne protège plus
  que `/azureauth/` — une route de test isolée (retourne un texte simple
  confirmant l'authentification), sans impact sur les utilisateurs réels.
  Permet de revalider l'intégration Entra ID à tout moment sans la remettre
  en production.
- **Nouvelle (Google)** : `127.0.0.1:4181`, service systemd dédié
  `oauth2-proxy-google.service`, config
  `/etc/oauth2-proxy/oauth2-proxy-google.cfg` (`600 oauth2-proxy:oauth2-proxy`,
  contient `client_secret` et `cookie_secret` — **jamais commité**, hors
  périmètre de `docs-infra`). Préfixe `/oauth2-google/`, protège `/reports`
  (+ ses deux routes SSE) et `/headscale-admin` via `auth_request` nginx.
  Utilisateurs autorisés : `/etc/oauth2-proxy/authorized_emails_google.txt`
  (liste blanche d'e-mails, surveillée par oauth2-proxy — l'ajout d'un
  utilisateur ne nécessite pas de redémarrage).

**Restent en basic auth** (accès script/appareil, pas de navigateur
interactif) : `/reports/webdav` (`scanz`, `pdfsync`) et `/pdf` (écriture,
`pdfsync`) — `/etc/nginx/.auth.allow`, inchangé.

### Piège rencontré : `proxy_prefix` par défaut

En configurant la 2ᵉ instance sur un chemin externe `/oauth2-google/`
différent du défaut, **le préfixe interne d'oauth2-proxy reste `/oauth2`
tant que `proxy_prefix` n'est pas explicitement redéfini** dans le fichier
de config. Sans ce réglage, `/oauth2-google/auth` ne correspond à aucune
route connue de l'instance et retombe sur le gestionnaire générique
(`Proxy`), qui affiche la page de connexion complète avec un code **403**
au lieu du **401** attendu par `auth_request` — cassant la boucle
`error_page 401 = /oauth2-google/start?...`. Correction :
`proxy_prefix = "/oauth2-google"` dans
`/etc/oauth2-proxy/oauth2-proxy-google.cfg`.

**Leçon : toute nouvelle instance `oauth2-proxy` exposée sous un chemin
nginx non standard doit fixer `proxy_prefix` sur ce même chemin.**

### Comptes GitHub existants pour référence sudoers

Rien à voir avec l'auth ci-dessus, mais note utile : le même jour, un
fichier `/etc/sudoers.d/mariadb-temp` (NOPASSWD, en place depuis juillet,
nom laissant croire à un oubli) a été renommé en `mariadb-nopasswd` pour
refléter qu'il s'agit d'un choix assumé, pas d'un reliquat. Un
`/etc/sudoers.d/marc-nopasswd` a été créé le même jour pour le compte
personnel `marc`.

## 10 septembre 2026 (matin, suite 2) — 403 Google + UI `/reports` introuvable

### Symptôme rapporté par l'utilisateur

Après bascule sur Google (voir entrée précédente), tentative de connexion
réelle en navigateur : `403` sur `/oauth2-google/callback` juste après
l'écran de consentement Google.

### Cause n°1 : Service Worker de la PWA en concurrence avec le flux OAuth

Logs `oauth2-proxy-google` : entre l'appel initial à `/reports/` et le
retour du navigateur depuis Google, une requête parasite
`/oauth2-google/start?rd=/reports/sw.js` apparaît — le Service Worker déjà
installé (PWA `reports`) vérifie `sw.js` en tâche de fond à chaque
chargement de page, **indépendamment** de la navigation de l'utilisateur.
Comme `/reports/sw.js` était protégé par le même `auth_request` que le
reste, cet appel concurrent déclenche son propre flux `/start` et
**écrase le cookie CSRF** (`_oauth2_proxy_google_csrf`, `Path=/`) avant que
le navigateur ne revienne sur `/callback` pour le flux principal → erreur
oauth2-proxy `CSRF cookie ... was not found` → `403`.

**Fix** : `location = /reports/sw.js` et `location = /reports/manifest.json`
ajoutées dans `docs.deltathermic.be`, exemptées de `auth_request`
(ni l'un ni l'autre ne contient de donnée sensible — pratique standard pour
les PWA derrière un SSO).

### Cause n°2 (découverte en creusant, sans rapport avec l'auth) : `app.py` ne montait pas l'UI

En vérifiant comment `/reports` est réellement servi côté WSGI,
`application.mount('/reports/api', api_app)` était le **seul** montage
dans `app.py` — `ui_app` (défini dans `ui.py`, 18 routes : `/`, `/sw.js`,
`/manifest.json`, `/chantier/<id>`, `/nodes`, etc.) n'était monté nulle
part. Conséquence : **même après une authentification réussie, `/reports`
aurait renvoyé un 404** — l'UI n'était pas branchée sur le point d'entrée
WSGI depuis la reconstruction de `app.py` du 9 septembre (qui n'avait
rétabli que la route API, cf. entrée du 9 septembre après-midi ci-dessus).
Jamais remarqué faute de test de bout en bout après cet incident.

**Fix** : ajout de `from ui import ui_app` et
`application.mount('/reports', ui_app)` dans `app.py`. Testé avant
déploiement (`py_compile` + import réel dans le venv `/opt/venv/reports`,
18 routes chargées sans erreur). Ancienne version conservée :
`app.py.bak_20260910_avant_mount_ui`. Rechargement ciblé de l'app
`reports` uniquement via `kill -HUP <pid>` (pas `service uwsgi ...`, cf.
incident du matin même) — trafic API réel (boîtiers) non interrompu
pendant l'opération.

**Leçon commune aux deux causes : après tout changement touchant
l'authentification ou le point d'entrée WSGI de `reports`, tester le
parcours complet en navigateur réel (pas seulement `curl`), y compris le
comportement d'arrière-plan d'une PWA déjà installée (Service Worker).**

## 10 septembre 2026 (après-midi) — Mise en place de l'interface de dev `/reports-dev`

Première étape concrète de la refonte décrite dans
`CAHIER-DES-CHARGES-REFONTE.md` (§11) : une interface de dev tourne
désormais en permanence à côté de la prod, sans aucune coupure ni
modification du code de production.

### Mis en place

- Copie de travail Git dans `/opt/reports-dev` (dépôt local, distinct de
  `docs-infra`), destinée à devenir l'environnement de dev permanent de
  la refonte plutôt qu'un simple répertoire jetable.
- Venv dédié `/opt/venv/reports-dev` (mêmes versions que la prod :
  bottle 0.13.1, PyMySQL 1.0.2, paho-mqtt 2.1.0) — `python3-venv` a dû
  être installé au préalable (absent du système).
- Base MariaDB séparée `dt_dev` (structure copiée de `dt` via
  `mysqldump --no-data`, aucune donnée réelle), utilisateur dédié
  `boitier_app_dev` à droits limités à `dt_dev`, secrets dans
  `/etc/boitier-fleet/db-dev.env` (mot de passe généré, distinct de la
  prod ; `FLEET_JOIN_SECRET` dev également distinct pour qu'aucun
  boîtier réel ne puisse s'enregistrer dessus par erreur).
- `app.py` et `db.py` (copie dev uniquement) lisent désormais
  `REPORTS_BASE_PATH` et `DB_ENV_FILE` depuis l'environnement, avec les
  mêmes valeurs par défaut qu'avant (`/reports`, `/etc/boitier-fleet/db.env`)
  — la prod n'est donc pas impactée.
- Nouvelle app uwsgi indépendante `reports-dev`
  (`/etc/uwsgi/apps-enabled/reports-dev.ini`, socket
  `/tmp/uwsgi.reports-dev.socket`, PID dans
  `/run/uwsgi/app/reports-dev/pid`), démarrée manuellement via
  `start-stop-daemon` (même mécanisme que celui utilisé par
  `/etc/init.d/uwsgi`, mais ciblé sur cette seule app, jamais
  `service uwsgi start/restart`) pour ne prendre aucun risque sur
  `reports` ni `headscale-admin`, déjà en cours d'exécution.
- Blocs nginx symétriques à ceux de `/reports` pour `/reports-dev`
  (même `auth_request` Google, mêmes exemptions PWA `sw.js`/`manifest.json`,
  même route SSE), ajoutés après sauvegarde horodatée
  (`docs.deltathermic.be.bak_20260910_122528_ajout_reports_dev`) et
  validés par `nginx -t` avant `systemctl reload nginx`.
- Bandeau visuel orange dans `layout.tpl` (copie dev uniquement),
  affiché sur toutes les pages servies sous `/reports-dev`.

### Vérifié

- PID des processus `reports` (prod) strictement inchangés avant/après
  toute l'opération ; `/reports/api/usage` toujours `200` à la fin.
- `/reports-dev/` redirige vers l'authentification Google comme
  `/reports/` ; `/reports-dev/api/usage` répond sans authentification
  (même politique que la prod, destinée aux boîtiers de test) ;
  `/reports-dev/sw.js` exempté comme prévu.

### Connu, non traité

- Certains chemins statiques du template (`layout.tpl`) restent en dur
  sur `/reports/static/...`, `/reports/manifest.json` : sans impact
  fonctionnel ou de sécurité (contenu public identique des deux côtés),
  mais à corriger lors du découpage en `core/paths.py` prévu par le
  cahier des charges.
- `python3-venv` n'était pas installé sur le serveur avant cette
  intervention ; `apt-get install` a signalé des redémarrages de services
  système différés (dbus, getty, networkd-dispatcher, logind,
  unattended-upgrades) sans rapport avec `reports` — non traités
  volontairement pour ne pas risquer d'impacter la prod hors périmètre
  de cette tâche.

## 10 septembre 2026 (fin d'après-midi) — core/config.py, core/database.py, core/paths.py

Suite de la refonte dans `/opt/reports-dev` (§4/§6 du cahier des
charges). Deux étapes, la seconde ayant révélé un vrai bug.

### core/config.py et core/database.py

Extraction sans surprise : `DB_ENV_FILE`/`REPORTS_BASE_PATH` centralisés
dans `core/config.py`, `get_db()` déplacé dans `core/database.py`,
l'ancien `db.py` supprimé. `api.py`, `ui.py` et les scripts annexes
mis à jour. Validé par `py_compile` + import réel du module `app`.

### core/paths.py — bug réel trouvé en cours de route

En préparant `core/paths.py` (chemins calculés depuis `__file__`, sur
le modèle `rpinode`), découverte que `ui.py` pointait **en dur** vers
`/var/www/reports/views` et `/var/www/reports/static`
(`TEMPLATE_PATH.append(...)`, `static_file(..., root=...)`). Conséquence
concrète : depuis sa mise en place, `/reports-dev` affichait en réalité
les templates et fichiers statiques de **production**, pas ceux de
`/opt/reports-dev` — la copie de travail n'était donc pas isolée comme
prévu. Plus grave : la console SQL de la page `/dev` postait vers
`fetch('/reports/sql', ...)` en dur, donc **exécutait ses requêtes sur
la base de production (`dt`) au lieu de `dt_dev`**, quel que soit
l'environnement affiché à l'écran.

Ce n'était pas visible dans les tests précédents (`curl` sur les codes
HTTP uniquement) — exactement le type d'angle mort déjà identifié le
10 septembre matin sur l'incident PWA/OAuth (« tester le parcours
complet, pas seulement `curl` »).

**Fix** : `core/paths.py` calcule `VIEWS_DIR`/`STATIC_DIR`/`WEBDAV_DIR`
à partir de l'emplacement réel du fichier, et tous les usages de
`/reports` comme préfixe de l'app elle-même (statics, manifest, icône,
en-tête `Service-Worker-Allowed`, console SQL, texte de doc) utilisent
désormais `core.config.BASE_PATH`. Vérifié par un appel WSGI direct de
la route `/dev` (`sudo -u mariadb`, pour lire `db-dev.env` avec les
mêmes droits que le vrai process uwsgi) confirmant `fetch('/reports-dev/sql'`
et des liens `manifest`/`apple-touch-icon` sous `/reports-dev/`, puis
par un test de bout en bout via nginx. PID de `reports` (prod)
vérifiés inchangés avant/après.

**Leçon à retenir pour la suite de la refonte** : chercher
systématiquement les chemins et préfixes en dur (`grep -n "/var/www/reports\|/reports/"`)
avant de considérer un module « terminé », l'ancien code n'ayant jamais
été pensé pour tourner ailleurs qu'à son unique emplacement de
production historique.

## 10 septembre 2026 (soir) — eclatement d'api.py en web/api.py + services/*.py

Suite de la refonte dans `/opt/reports-dev` (§6 du cahier des charges).
Le plus gros morceau du monolithe : `api.py` (1696 lignes, 16 routes)
devient `src/web/api.py` (assemblage, routes transverses `/usage`, hook
avant-requete, gestion d'erreurs) + 6 modules `src/services/*.py`
(`fleet`, `chantiers`, `sync`, `trends`, `logs`, `headscale`), chacun
regroupant les routes d'un domaine et les helpers prives qui ne servent
qu'a lui (ex. les 7 `_push_*` de `/sync` restent avec `/sync`).

### Choix d'architecture assumé

Par prudence (pas de suite de tests automatisée pour rattraper une
régression subtile), le découpage sépare **par domaine**, pas encore
**logique métier vs routage HTTP** comme le visait littéralement le
critère d'acceptation §9 du cahier des charges (« api.py ne contient plus
que du routage ») : chaque fonction de route reste telle quelle (ouvre sa
connexion DB, lit `request.json`/`request.query`, appelle `json_ok`/
`json_error`), simplement déplacée dans le fichier de son domaine. Aller
jusqu'à la séparation complète (fonctions de service pures sans `bottle`,
routage qui ne fait que parser/formater) aurait multiplié le risque de
régression pour un gain immediat plus faible que « sortir du fichier
unique de 1696 lignes ». A reconsiderer une fois `tests/` construit
(objectif 3 du cahier des charges).

### Effet de bord trouvé et corrigé : la page /dev

`ui.py` (onglet « api » de la page `/dev`) faisait `import api` puis
relisait le code source ligne par ligne pour retrouver le décorateur
`@api_app.get`/`post` au-dessus de chaque fonction (`inspect.getsourcelines`).
Cassé mécaniquement par l'éclatement (plus de module `api` unique à
inspecter). Remplacé par une introspection de `api_app.routes`
(`route.rule`, `route.method`) : plus robuste, plus simple, et c'est
exactement le même principe que `global_usage()` utilisait déjà dans
`api.py` d'origine pour `/usage` — les deux mécanismes de doc auraient
dû être unifiés depuis longtemps.

### Vérifié

- `py_compile` sur tout le projet.
- Import réel du module `app` en `sudo -u mariadb` (mêmes droits que le
  vrai process uwsgi) : 16/16 routes API et 18/18 routes UI présentes,
  identiques à avant l'éclatement.
- Appels WSGI directs `GET /ping` et `GET /api/usage` : 200, contenu
  correct.
- Page `/dev?tab=api` : mêmes routes documentées qu'avant, **y compris
  les mêmes trous préexistants** (`headscale_enroll`, `headscale_routes`,
  `register_auto` utilisaient déjà « Reponse: » sans accent dans leur
  docstring dans l'ancien `api.py`, donc déjà absents de cette page avant
  toute refonte — non regressé, juste déplacé tel quel).
- Test de bout en bout via nginx (`/reports-dev/api/ping`,
  `/reports-dev/api/usage`, `/reports-dev/sw.js`) après rechargement
  ciblé (`kill -HUP` sur le PID de `reports-dev` uniquement).
- PID de `reports` (prod) vérifiés inchangés avant/après.

### Nettoyage connexe

Suppression de `test_api_mqtt.py` (script de debug de 2 lignes,
`import api` devenu sans objet, plus aucune valeur).

## 10 septembre 2026 (soir, suite) — « Utilisateur introuvable » sur /reports-dev

### Symptôme

Après connexion Google réussie sur `/reports-dev/`, page blanche avec le
seul texte « Utilisateur introuvable. »

### Cause

`dt_dev` a été créée via `mysqldump --no-data` (structure seule, aucune
donnée réelle copiée — choix délibéré pour ne jamais exposer de vraies
données clients/personnel dans un environnement de dev moins protégé).
`ui.py::reports_root()` cherche par défaut `utilisateurs WHERE id = 1`
(paramètre `uid` absent de l'URL) : la table est vide dans `dt_dev`, la
route retourne donc explicitement « Utilisateur introuvable. » —
comportement de l'application, pas un bug de la refonte.

**Note** : `chantiers` et `boitier_registre` sont également vides dans
`dt_dev` (structure seule) — attendu, l'accueil affichera une liste de
chantiers vide tant qu'aucune donnée de test n'y est insérée.

### Fix

Un utilisateur de dev synthétique (pas une copie d'un vrai compte) a été
inséré dans `dt_dev.utilisateurs` :

```sql
INSERT INTO dt_dev.utilisateurs (id, ref, nom, cas, adm)
VALUES (1, 'dev', 'Utilisateur Dev', 1, 1);
```

Vérifié par appel WSGI direct (`sudo -u mariadb`) : `GET /reports-dev/`
renvoie `200`, contient « Utilisateur Dev », ne contient plus
« Utilisateur introuvable ». Prod non touchée (aucune action sur `dt`).

### Pour la suite

Si des tests plus poussés de l'UI de dev nécessitent des chantiers/boîtiers
de test, insérer des données synthétiques équivalentes dans `dt_dev`
(jamais copier de vraies lignes depuis `dt`).

## 10 septembre 2026 (nuit) — eclatement d'ui.py en web/ui.py + web/stream.py + services/templates_maintenance.py

Suite et fin (provisoire) du découpage par domaine du §6 du cahier des
charges. `ui.py` (1169 lignes, 18 routes) suit le même principe qu'`api.py` :
même nuance assumée (routage et logique restent ensemble par route), mais
cette fois la majorité du fichier reste groupée dans `web/ui.py` (accueil,
pages chantier, nœuds, console SQL, page `/dev`) — seuls deux sous-domaines
étaient assez autonomes pour justifier un fichier à part :

- `web/stream.py` : les 2 routes SSE (`reports_sse`,
  `chantier/<id>/reports_sse`), qui relaient les messages du broker MQTT
  local sans toucher à la base de données.
- `services/templates_maintenance.py` : vue d'ensemble des templates
  Modbus partagés, diff entre deux révisions, dépréciation, suppression.

### Bug réel trouvé et corrigé : le bandeau dev ne s'affichait jamais

En testant la page d'accueil après l'éclatement (`GET /`), le bandeau
visuel orange ajouté le 10 septembre après-midi (§11 du cahier des
charges) était absent. Cause : sa condition
(`bottle.request.path.startswith('/reports-dev')`) ne peut **jamais**
fonctionner une fois l'application montée par Bottle — à l'intérieur d'un
sous-app monté, `request.path` est **relatif au point de montage**
(vérifié par un appel WSGI direct sur une route de debug temporaire :
`/reports-dev/__debug_path` devient `'/__debug_path'` côté `ui_app`).
Le bandeau n'a donc jamais pu s'afficher depuis sa création, mais ça n'avait
jamais été remarqué faute d'avoir testé le rendu HTML complet à l'époque
(seulement la présence de la chaîne dans le fichier source).

**Fix** : condition remplacée par `core.config.BASE_PATH != '/reports'`,
indépendante de tout comportement de montage. Vérifié dans les deux sens
(bandeau présent avec `REPORTS_BASE_PATH=/reports-dev`, absent sans cette
variable — donc absent en configuration équivalente à la prod).

**Leçon** : `bottle.request.path` (et plus largement tout ce qui dépend du
WSGI `PATH_INFO`/`SCRIPT_NAME`) n'est **pas fiable** pour détecter le
préfixe de montage externe d'une sous-application Bottle. Préférer une
valeur explicite connue à l'avance (ici `core.config.BASE_PATH`).

### Vérifié

- `py_compile` sur tout le projet.
- Import réel du module `app` (`sudo -u mariadb`) : 16/16 routes API et
  18/18 routes UI identiques à avant l'éclatement.
- Appels WSGI directs : `GET /` (contient le bandeau dev et l'utilisateur
  de dev), `GET /dev?tab=api`, `GET /nodes`, `GET /maintenance/templates`.
- Test de bout en bout via nginx après rechargement ciblé (`kill -HUP`
  sur le PID de `reports-dev` uniquement).
- PID de `reports` (prod) vérifiés inchangés avant/après.

## 11 septembre 2026 — vraie suite de tests pytest, run.sh/run_tests.sh

Objectif 3 du cahier des charges. `tests/` (pytest) remplace les
anciens scripts de débogage à la racine (`test_bottle_*.py`,
`test_mount.py`, `test_server.py`, `test_uwsgi.py`, `test_db.py`,
`test_sync.py` racine) : aucun n'avait d'assertion, juste des `print()`
à relire à la main. Supprimés.

### Contenu

- `conftest.py` + `_helpers.py` : `call_wsgi()` appelle l'application
  WSGI **directement**, comme le fait réellement uwsgi (montage complet,
  hooks Bottle compris) — plus fidèle qu'appeler les fonctions de route
  une par une. C'est justement l'absence de ce type de test qui a laissé
  passer l'incident du 10 septembre (UI non montée).
- `test_wsgi_mount.py` : non-régression directe de cet incident, plus un
  garde-fou sur le nombre de routes enregistrées (16 API, 18 UI) pour
  attraper une perte accidentelle lors d'un futur refactor.
- `test_core_paths.py` : non-régression du bug du 10 septembre soir
  (`ui.py` servait les fichiers de production).
- `test_pwa_exemptions.py` : non-régression de l'incident CSRF/Service
  Worker, plus une vérification que `Service-Worker-Allowed` suit
  `BASE_PATH` (aurait été figé à `/reports/` sans le fix du 10 septembre).
- Un fichier par domaine `services/` : couvrent au minimum le refus
  (401/403) sans authentification ; `test_fleet.py` va plus loin avec un
  cycle complet d'enregistrement contre `dt_dev` (hostname/cpu_serial
  uniques par exécution, `dt_dev` ne contenant aucune donnée réelle il
  n'y a pas besoin de nettoyage après coup).

### run_tests.sh / run.sh

Déduisent le venv et le nom de l'app uwsgi **du nom du dossier courant**
(`reports-dev` ici → `/opt/venv/reports-dev` + PID
`/run/uwsgi/app/reports-dev/pid` ; `reports` une fois ce checkout promu
en production → memes chemins avec "reports") : même convention que les
fichiers uwsgi déjà en place, donc réutilisables tels quels après
promotion sans édition manuelle.

`run_tests.sh` doit impérativement s'exécuter en `sudo -u mariadb` :
`/etc/boitier-fleet/db-dev.env` n'est lisible que par ce compte (mêmes
droits que le vrai process uwsgi). Lancé en `marc`/`docsadmin`, `core.config`
eéchoue silencieusement à lire le fichier et retombe sur les identifiants
par défaut, faisant échouer tous les tests touchant la base de façon
trompeuse (documentation dans `tests/README.md`).

`run.sh` : `py_compile` puis suite de tests puis, seulement si tout est
vert, `kill -HUP` ciblé (jamais `service uwsgi ...`). **Vérifié
manuellement** que le garde-fou fonctionne reellement : un test cassé
volontairement (erreur à la collection) bloque bien le rechargement,
message clair affiché, code de sortie non nul, l'app en cours reste
active et servie normalement pendant l'échec.

### Vérifié

- 32/32 tests passent.
- Garde-fou de `run.sh` testé en conditions réelles (échec volontaire
  provoqué puis retiré), `reports-dev` jamais interrompu pendant le test.
- Prod non touchée.

## 11 septembre 2026 (suite) — nettoyage final : migrations, templates/, docs/, README.md

Dernier lot du §6 du cahier des charges côté organisation (le
découpage logique/routage complet reste reporté, voir plus haut).

- `sql_script.py`/`.sql`, `schema_update.sql` (migrations ponctuelles
  déjà appliquées le 8 septembre : renommage
  `boitier_annotations` -> `boitier_fabricants`) déplacées vers
  `tools/migrations/`, datées et documentées.
- `views/` renommé en `templates/` (cohérence de vocabulaire avec
  `rpinode`) ; `core/paths.py` expose `TEMPLATES_DIR`.
- Ce fichier (`NOTES-evolutions.md`) et `HEADSCALE-ACL.md` déplacés
  vers `docs/operations/` et `docs/incidents/` — **même mouvement
  appliqué en production** (déplacement de documentation pure, aucun
  impact fonctionnel, vérifié par un appel a `/reports/api/usage`
  immédiatement après).
- `docs/README.md` et `tools/README.md` ajoutés (index, sur le modèle
  `rpinode`).
- `README.md` racine entièrement réécrit (était quasiment vide depuis
  le début du projet) : architecture réelle, comment lancer les tests
  et redémarrer en sécurité, description de l'interface de dev.

### Vérifié

- `./run.sh` complet (py_compile + 32/32 tests + rechargement ciblé)
  après chaque changement.
- PID de `reports` (prod) vérifiés inchangés.

### État du cahier des charges après cette série de commits

Tous les objectifs organisationnels du §4 sont atteints dans
`/opt/reports-dev`, sauf la bascule en production elle-même (§7) qui
reste à faire quand ce sera décidé, et la séparation complète
logique/routage (reportée, voir plus haut et §9 du cahier des
charges).

## 11 septembre 2026 (suite) — dt_dev peuplée par un dump reel de dt

Décision explicite (Marc) : « pas de risque à faire un dump des tables
de prod vers les tables de dev ». Revient sur le choix initial
(structure seule + utilisateur synthétique, §11 du cahier des charges)
— justifié par le fait que `/reports-dev` et `/reports` partagent
exactement le même périmètre d'accès (même authentification Google,
même liste blanche d'e-mails dans `authorized_emails_google.txt`) :
copier de vraies données n'élargit pas l'exposition par rapport à la
production elle-même.

### Opération

1. **Constat préalable** : `dt_dev.boitier_registre` contenait des
   résidus des propres tests automatisés (`rpi01`..`rpi08` générés par
   `test_register_auto_avec_secret_attribue_un_hostname_rpiNN` à chaque
   exécution depuis une base vide, plus des `test-*` de
   `test_register_avec_secret_...`). Ces `rpiNN` seraient entrés en
   collision avec les vrais hostnames de la flotte lors du chargement
   du dump.
2. **Purge propre** : `DROP DATABASE dt_dev` puis
   `CREATE DATABASE dt_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`
   (plutôt que des `TRUNCATE` table par table, plus simple et plus
   sûr contre les contraintes de clés étrangères).
3. **Chargement** : `mysqldump --routines --triggers dt | mysql dt_dev`
   (structure + données en un seul passage, cohérent avec la méthode
   utilisée pour la création initiale structure-seule).
4. **Droits** : `GRANT ALL PRIVILEGES ON dt_dev.*` étant lié au nom du
   schéma (pas à un identifiant interne), `DROP`/`CREATE DATABASE` ne
   fait perdre aucun droit — vérifié (`SHOW GRANTS FOR
   'boitier_app_dev'@'localhost'` identique avant/après).

### Vérifié

- Comptes de lignes identiques entre `dt` et `dt_dev` sur les tables
  clés (`utilisateurs` 6/6, `chantiers` 13/13, `boitier_registre` 1/1,
  `boitier_trends` 110807/110807).
- L'utilisateur par défaut (`uid=1` coté `ui.py::reports_root()`) existe
  bel et bien dans les vraies données (« Marc Fache ») : plus besoin de
  l'utilisateur de dev synthétique créé le 10 septembre.
- `./run_tests.sh` : 32/32 toujours au vert avec les vraies données en
  place (les tests utilisent des hostnames/cpu_serial aléatoires par
  exécution, aucune collision avec les vraies données).
- Test de bout en bout via nginx (`/reports-dev/api/ping`,
  `/reports-dev/api/usage`) après l'opération.
- PID de `reports` (prod) vérifiés inchangés — opération purement au
  niveau de la base, aucun redemarrage necessaire cote prod.

### Documentation mise à jour en conséquence

Le bandeau visuel de dev (`templates/layout.tpl`) affirmait « données
non réelles » — devenu faux, corrigé en « base dt_dev, jamais la
production » (affirmation qui reste vraie indépendamment du contenu des
données). `README.md` et `CAHIER-DES-CHARGES-REFONTE.md` §11 mis à jour
pour ne plus affirmer l'absence de vraies données dans `dt_dev`.

### Pour la suite

`dt_dev` n'est **jamais** écrite en retour vers `dt` et divergera
naturellement de la production au fil des tests (c'est le but). La
resynchroniser au besoin par le même processus (étapes 2-3
ci-dessus).

## 10 septembre 2026 (fin de journée) — système « poupée russe », dynamisation des URLs et emails utilisateurs

### Système de Template « Poupée Russe »
Portage du moteur de template de `rpinode` (rpi01) vers `reports`.
- Création de `src/web/templating.py` : centralise la logique de rendu et gère l'emboîtement automatique (Layout > Page > Fragment).
- Support HTMX natif : les requêtes avec le header `HX-Request` ne reçoivent plus que le fragment HTML utile (accélération de la navigation et économie de bande passante).
- Injection automatique des variables globales (`BASE_PATH`, `current_user`, `all_users`) dans tous les templates, simplifiant drastiquement les contrôleurs dans `ui.py`.
- Suppression des `% rebase` dans les templates individuels au profit d'un emboîtement piloté par le Python.

### Dynamisation des URLs
- Éradication des chemins codés en dur (`/reports/`) dans tous les templates et scripts JS.
- Utilisation systématique de la variable `BASE_PATH` (configurable via `REPORTS_BASE_PATH`) pour garantir la portabilité totale du code entre `/reports` (prod) et `/reports-dev` (dev).
- Ajout de l'onglet **Environnement** dans l'espace `/dev` pour inspecter les variables d'environnement du processus.

### Identification et Emails utilisateurs
- Confirmation de la source de vérité pour l'accès OAuth2 : la liste blanche se trouve dans `/etc/oauth2-proxy/authorized_emails_google.txt` (vérifié : contient uniquement `marc@fache.be`).
- Création de la table `utilisateurs_emails` dans MariaDB (appliqué sur `dt` et `dt_dev`) :
    - Permet de lier plusieurs adresses email à un même utilisateur (support des alias).
    - Initialisée avec `marc@fache.be` lié à l'ID 1 (Marc Fache).
    - Migration enregistrée dans `tools/migrations/20260910_add_user_emails.py`.
- **Auto-enregistrement des nouveaux utilisateurs** : Si un email authentifié via OAuth2 n'est pas reconnu en base, un compte est automatiquement créé avec le statut "En attente" (`cas=0`, `adm=0`). La référence (`ref`) est générée avec le préfixe `WAIT_` suivi d'un hash court pour garantir l'unicité.

### Problèmes rencontrés et résolus lors de cette phase

#### 1. Piège de l'environnement DB par défaut
- **Problème** : La première exécution du script de migration `20260910_add_user_emails.py` a ciblé la base de production (`dt`) alors que je travaillais dans `/opt/reports-dev`. Le fichier `/etc/boitier-fleet/db.env` est lu par défaut si `DB_ENV_FILE` n'est pas spécifié.
- **Résolution** : Identification immédiate via `SHOW TABLES`. Application manuelle à la base de dev via `sudo -u mariadb env DB_ENV_FILE=/etc/boitier-fleet/db-dev.env python3 ...`.
- **Leçon** : Toujours expliciter le fichier d'environnement lors de l'exécution de scripts de maintenance en mode "double instance".

#### 2. Régressions lors de l'abandon de `% rebase`
- **Problème** : Le passage au helper `view()` a provoqué des `NameError` dans `services/templates_maintenance.py` (variables manquantes et imports `request`/`response` oubliés après nettoyage).
- **Résolution** : Détection rapide par `./run.sh` (échec des tests de maintenance). Correction des imports et remise en place du `json.dumps` nécessaire avant l'appel à la vue.
- **Leçon** : Ne jamais présumer qu'un nettoyage "cosmétique" est anodin. La suite de tests a ici parfaitement joué son rôle de filet de sécurité.

#### 3. Accès documentaire sur `rpi01`
- **Problème** : Nécessité de consulter la définition exacte du système "poupée russe" sur une machine distante (`rpi01`).
- **Résolution** : Utilisation de `ssh docsadmin@rpi01` combiné à `sudo` pour lire `src/web/templating.py` et les fichiers `.md` locaux.
- **Leçon** : L'accès `docsadmin` est vital pour maintenir la cohérence entre le serveur maître et les boîtiers de terrain.

#### 4. Distinction entre identité réelle et simulée (Admin Switcher)
- **Problème** : Après avoir implémenté le switcher d'utilisateur pour l'admin, le menu disparaissait dès qu'on switchait vers un utilisateur non-admin. Le système considérait que l'utilisateur actuel n'avait plus les droits de voir le switcher.
- **Résolution** : Séparation de la logique de résolution en deux entités : `real_user` (déterminé par l'email OAuth2) et `current_user` (celui simulé par `?uid=X`). Le layout utilise désormais `real_user.is_admin` pour maintenir l'affichage des outils d'administration et du switcher, quel que soit le profil simulé.
- **Leçon** : Toujours conserver une trace de l'identité forte (authentifiée) pour ne pas s'enfermer dans un rôle simulé dont on ne peut plus sortir.

#### 5. Conflit de priorité entre Email et UID
- **Problème** : L'email OAuth2 était prioritaire sur le paramètre `uid`, rendant le switcher inopérant pour l'administrateur authentifié.
- **Résolution** : Inversion de la priorité uniquement pour les administrateurs : si un `uid` est présent dans l'URL et que l'utilisateur authentifié est Admin, le `uid` prend le dessus pour la session de rendu.

### Vérifié
- `./run.sh` : 33/33 tests passés avec succès.
- Rechargement uwsgi effectué : les nouvelles fonctionnalités sont actives sur `/reports-dev`.
