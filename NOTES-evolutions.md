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
