# Headscale — topologie réseau, ACL et SSH

Documentation de l'infrastructure Tailscale/Headscale de
`docs.deltathermic.be`, écrite après l'incident du 09/09/2026 (perte
d'accès SSH à `rpi01` suite à l'activation de Tailscale SSH). À tenir à
jour à chaque modification de `acl.hujson`.

## 1. Topologie actuelle

| Nœud (hostname)  | Nom réseau     | Utilisateur Headscale | Tag         | Rôle |
|-------------------|----------------|------------------------|-------------|------|
| DESKTOP-BUREAU     | desktop-h66    | delta                  | -           | Poste perso |
| docs (ce serveur)  | docs           | tagged-devices         | `tag:docs`  | Serveur Headscale + admin (reports, headscale-admin) |
| rpi01              | rpi01          | tagged-devices         | `tag:fleet` | Raspberry Pi de terrain (`rpinode.service`) |
| MW-001-MSZ-ZZ      | laptop-marc    | delta                  | -           | Poste perso (celui d'où on administre) |

- **`delta`** est l'utilisateur Headscale "humain" (compte réseau), propriétaire des postes personnels.
- **`tagged-devices`** est l'utilisateur virtuel automatique de Headscale dès qu'un nœud porte un tag (`docs`, `rpi01`). Une fois taggé, un nœud n'appartient plus à un utilisateur Headscale classique.
- Les tags sont posés via `headscale nodes tag -i <ID> -t tag:xxx`.

## 2. Fichier `acl.hujson`

Emplacement : `/etc/headscale/acl.hujson`
Chargé si `policy.mode: file` et `policy.path` le pointe (dans `config.yaml`).

### 2.1 Comptes systèmes créés pour l'automatisation entre machines

| Compte OS | Machine | Verrouillé (`passwd -l`) | Clés SSH classiques | Sudo |
|---|---|---|---|---|
| `fleet` | docs | oui | aucune | aucun |
| `docsadmin` | rpi01 | oui | aucune | restreint (voir `/etc/sudoers.d/docsadmin` sur rpi01 : status/restart de `rpinode(.service                                                                                                             )`/`rpinode-supervisor.service`, `journalctl`, `tailscale status`) |

Ces comptes n'ont **ni mot de passe ni clé SSH** : leur seule porte d'entrée est l'identité réseau Tailscale/Headscale (`tailscale ssh`), autorisée exclusivement par la section `"ssh"` ci-dessous.

### 2.2 Section `"ssh"` — qui a le droit de se connecter en SSH, et en tant que qui

```json
"ssh": [
  { "action": "accept", "src": ["tag:fleet"],           "dst": ["tag:docs"],  "users": ["fleet"] },
  { "action": "accept", "src": ["tag:docs"],            "dst": ["tag:fleet"], "users": ["docsadmin"] },
  { "action": "accept", "src": ["group:fleet-admins"],  "dst": ["tag:fleet"], "users": ["marc"] },
  { "action": "accept", "src": ["group:fleet-admins"],  "dst": ["tag:docs"],  "users": ["mariadb"] }
]
```

| Règle | Depuis | Vers | Login autorisé | Usage |
|---|---|---|---|---|
| 1 | `rpi01` (tag:fleet) | `docs` (tag:docs) | `fleet` | Automatisation rpi01 → docs |
| 2 | `docs` (tag:docs) | `rpi01` (tag:fleet) | `docsadmin` | Automatisation docs → rpi01 (supervision restreinte) |
| 3 | `group:fleet-admins` (= `delta@`) | `rpi01` (tag:fleet) | `marc` | **Accès admin humain** sur rpi01 (ajoutée le 09/09/2026) |
| 4 | `group:fleet-admins` (= `delta@`) | `docs` (tag:docs) | `mariadb` | **Accès admin humain** sur docs (ajoutée le 09/09/2026) |

**Point crucial** : dès qu'un nœud active `tailscale set --ssh`, c'est **exclusivement** cette liste qui décide qui peut ouvrir une session SSH, et sous quel login. Le `sshd` classique, les `authorized_keys`, les mots de passe système : tout ça est contourné/ignoré pour les connexions qui passent par le réseau Tailscale. Une règle absente = accès refusé, sans exception, même pour root/l'admin habituel.

### 2.3 `tagOwners` et `groups`

```json
"groups": { "group:fleet-admins": ["delta@"] },
"tagOwners": {
  "tag:fleet": ["group:fleet-admins"],
  "tag:docs": ["group:fleet-admins"]
}
```

`delta` est le seul autorisé à poser/retirer les tags `tag:fleet` et `tag:docs` sur un nœud.

### 2.4 Section `"acls"` (trafic réseau, pas SSH)

```json
"acls": [{ "action": "accept", "src": ["*"], "dst": ["*:*"] }]
```

Actuellement complètement ouverte (tout le tailnet communique librement sur tous les ports). Seule la section `"ssh"` est restrictive.

## 3. Incident du 09/09/2026 — perte d'accès SSH à `rpi01`

### Chronologie
1. Mise en place des tags (`rpi01` → `tag:fleet`, `docs` → `tag:docs`) et des comptes techniques `fleet`/`docsadmin`.
2. Activation du SSH natif Tailscale sur `rpi01` : `tailscale set --ssh`, puis, après avertissement, `tailscale set --ssh --accept-risk=lose-ssh`.
3. Déconnexion immédiate : `client_loop: send disconnect: Connection reset`, puis perte totale de la session SSH en cours sur `rpi01`.

### Cause racine
Le flag `--accept-risk=lose-ssh` n'apparaît **que lorsque Tailscale détecte lui-même** qu'aucune règle de la policy `"ssh"` active ne permettrait à la session en cours de se rouvrir après le changement. À ce moment-là, seules les règles 1 et 2 existaient : aucune n'autorisait un compte admin humain (`delta`/`marc`) à se connecter à `rpi01`. Le risque annoncé par l'outil s'est donc produit exactement comme prévu.

### Ce qui n'a PAS été cassé
- Le tunnel WireGuard / la connectivité réseau Tailscale : intacte tout du long (`ping`, `tailscale status`, nœud `online: true`).
- Le service métier sur `rpi01` (`rpinode.service`) : jamais interrompu.
- Le chemin `docs → docsadmin` (règle 2) : resté fonctionnel, il a servi de porte de secours pour diagnostiquer sans toucher à `rpi01`.

### Correctif appliqué
Ajout des règles 3 et 4 ci-dessus dans `acl.hujson`, validées avec `headscale policy check -f <fichier>` avant application, puis rechargées avec `systemctl restart headscale` (mode `policy.mode: file`, pas de `headscale policy set` possible dans ce mode).

Sauvegarde de l'ancien fichier conservée : `/etc/headscale/acl.hujson.bak_before_ssh_fix_20260909_133320`.

## 4. Procédure de récupération si l'accès SSH admin se perd à nouveau

1. **Ne pas paniquer sur la connectivité réseau** : vérifier d'abord que le nœud est toujours joignable au niveau tunnel :
   ```
   sudo headscale nodes list -o json   # online: true ?
   tailscale ping <nom-du-noeud>
   ```
   Si oui, le problème est très probablement uniquement dans la section `"ssh"` de l'ACL, pas une panne réelle.

2. **Chercher un chemin de secours déjà autorisé** dans `acl.hujson` (`headscale policy get`) : un autre nœud/tag/compte qui a le droit d'entrer.

3. **Depuis ce chemin de secours**, utiliser `tailscale ssh <compte_autorisé>@<noeud>` (pas `ssh` classique, qui est ignoré une fois Tailscale SSH actif).

4. **Corriger `acl.hujson`** en ajoutant une règle `"ssh"` pour le compte/groupe qui doit récupérer l'accès admin. Toujours :
   - sauvegarder l'ancien fichier avant d'écraser (`cp acl.hujson acl.hujson.bak_<horodatage>`) ;
   - valider avec `headscale policy check -f <nouveau_fichier>` avant de remplacer le fichier en place ;
   - recharger avec `systemctl restart headscale` (mode `file`) — **aucune action requise sur le nœud distant**, la policy est évaluée côté serveur à chaque connexion.

## 5. Bonnes pratiques pour la suite

- **Ne jamais activer `tailscale set --ssh` sur un nouveau nœud sans avoir d'abord vérifié/ajouté, dans `acl.hujson`, une règle explicite couvrant le compte admin humain habituel** vers le tag de ce nœud. Le drapeau `--accept-risk=lose-ssh` est un avertissement à prendre au pied de la lettre, pas une formalité à contourner.
- Garder une règle "large" de secours par tag pour `group:fleet-admins`, comme les règles 3/4 ci-dessus, avant d'ajouter des règles plus fines/restrictives pour l'automatisation.
- Toute modification de `acl.hujson` : sauvegarde + `headscale policy check` avant application, jamais d'édition à chaud sans backup.
- Documenter ici toute nouvelle règle `"ssh"` ajoutée (qui, vers qui, pourquoi), pour qu'un incident futur se diagnostique en minutes et pas en heures.
