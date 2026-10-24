# Flux de travail Git & Synchronisation

Ce fichier documente l'architecture locale des dossiers et la marche à suivre pour sauvegarder (commit/push) le code sur le dépôt distant.

## 🏗️ L'architecture des dossiers

Lors de l'utilisation et du développement sur ce serveur, nous avons découvert que le code est scindé en deux concepts :

1. **Le bac à sable de développement (`/opt/reports-dev`)** : 
   C'est le dossier dans lequel nous travaillons activement, modifions les fichiers et testons les changements via l'application uWSGI locale (`reports-dev`). Il possède un `remote` (`origin` → `git@github-reports-dev:mfache/reports-dev.git`), mais ce dépôt n'est **pas** la référence : le code officiel est versionné dans `docs-infra` (voir ci-dessous).
   
2. **Le dépôt Git officiel (`/opt/docs-infra`)** :
   C'est ici que se trouve le véritable dépôt Git (`origin` pointe vers `git@github-reports:mfache/docs-infra.git`). Le code de notre application `reports` est versionné dans le sous-dossier `/opt/docs-infra/var/www/reports`.

## 🚀 Comment "Commit & Push" ses modifications ?

Puisque nous développons dans `/opt/reports-dev`, il faut synchroniser notre travail vers `/opt/docs-infra` avant de pouvoir faire un push.

Voici la procédure exacte (commandes à copier-coller) :

### 1. Commiter localement dans le bac à sable (Optionnel mais recommandé)
Ce dépôt local trace l'historique de travail du bac à sable. Un commit ici ne publie rien dans le dépôt officiel, et son `origin` (`mfache/reports-dev`) n'est pas mis à jour automatiquement.

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
*Note : un `git push` depuis `/opt/reports-dev` envoie uniquement vers `mfache/reports-dev`, pas vers le dépôt officiel. Pour publier le code de `reports`, il faut toujours passer par `docs-infra` (étapes 2 à 4).*