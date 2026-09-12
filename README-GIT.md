# Flux de travail Git & Synchronisation

Ce fichier documente l'architecture locale des dossiers et la marche à suivre pour sauvegarder (commit/push) le code sur le dépôt distant.

## 🏗️ L'architecture des dossiers

Lors de l'utilisation et du développement sur ce serveur, nous avons découvert que le code est scindé en deux concepts :

1. **Le bac à sable de développement (`/opt/reports-dev`)** : 
   C'est le dossier dans lequel nous travaillons activement, modifions les fichiers et testons les changements via l'application uWSGI locale (`reports-dev`). **Ce dossier n'est pas directement relié au dépôt Git distant** (aucun `remote` n'est configuré).
   
2. **Le dépôt Git officiel (`/opt/docs-infra`)** :
   C'est ici que se trouve le véritable dépôt Git (`origin` pointe vers `git@github-reports:mfache/docs-infra.git`). Le code de notre application `reports` est versionné dans le sous-dossier `/opt/docs-infra/var/www/reports`.

## 🚀 Comment "Commit & Push" ses modifications ?

Puisque nous développons dans `/opt/reports-dev`, il faut synchroniser notre travail vers `/opt/docs-infra` avant de pouvoir faire un push.

Voici la procédure exacte (commandes à copier-coller) :

### 1. Commiter localement dans le bac à sable (Optionnel mais recommandé)
Même si ce dossier n'est pas relié à GitHub, il possède son propre dépôt Git local pour tracer votre historique de travail.

```bash
git add .
git commit -m "Description de la mise à jour locale..."
```

### 2. Synchroniser le bac à sable vers le dépôt Git
On utilise `rsync` pour copier nos modifications en excluant les dossiers inutiles (`.git`, `__pycache__`) :

```bash
rsync -av --delete --exclude='.git' --exclude='__pycache__' /opt/reports-dev/ /opt/docs-infra/var/www/reports/
```

### 3. Voir le statut des modifications (côté docs-infra)
On se déplace virtuellement dans le dépôt Git global pour voir ce qui a changé :

```bash
git -C /opt/docs-infra status
```

### 4. Ajouter, Commiter et Pusher (côté docs-infra)
On ajoute les fichiers du sous-dossier `reports`, on valide et on envoie sur GitHub :

```bash
git -C /opt/docs-infra add var/www/reports
git -C /opt/docs-infra commit -m "Description de la mise à jour..."
git -C /opt/docs-infra push
```

---
*Note: Ne jamais faire de `git push` directement depuis `/opt/reports-dev`, cela échouera car le dépôt distant officiel est géré par l'infrastructure globale dans `docs-infra`.*