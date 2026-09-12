# Instructions spécifiques pour le projet reports-dev

Vous êtes dans le bac à sable de développement de l'application `reports`. Le dépôt Git officiel relié à GitHub se trouve dans `/opt/docs-infra/var/www/reports`.

## Règles de développement
- L'interface de dev est accessible via l'application uWSGI `reports-dev`.
- Les modifications de base de données doivent se faire de préférence sur la base `dt_dev`, pas sur la base de production `dt`.

## Modèle de données & Fonctionnalités (Recherches consignées)
- **Affectation des Chantiers aux Utilisateurs** : L'attribution ne se fait pas via une table de jointure classique, mais via la table `filtres` (`utilisateurs_id`, `chantiers_id`, `ref` (nom du filtre), `tri`, `description`). Un utilisateur a accès à un chantier si un filtre lui est associé pour ce chantier.
- Les interfaces d'administration sont gérées dans `src/web/admin_users.py` et les templates associés (`admin_users.tpl`, `admin_chantiers_users.tpl`).

## Rechargement de l'application
Après toute modification du code Python, l'application uWSGI doit être rechargée pour que les changements soient visibles.
**ATTENTION : Ne jamais utiliser `service uwsgi restart` ou `systemctl`** (cela coupe toutes les applications du serveur, y compris la prod).

- Option 1 (recommandée) : Exécuter le script de validation locale `./run.sh`
- Option 2 (si le script échoue sur des faux positifs) : Rechargement manuel ciblé du worker dev :
  `sudo kill -HUP $(cat /run/uwsgi/app/reports-dev/pid)`

## Flux Git (Important)
Ne faites **jamais** de `git push` directement depuis ce dossier. 

Suivez obligatoirement le flux de travail décrit dans `README-GIT.md` :
1. Commit local dans `/opt/reports-dev`
2. `rsync` vers `/opt/docs-infra/var/www/reports/` (ex: `rsync -av --delete --exclude='.git' --exclude='__pycache__' /opt/reports-dev/ /opt/docs-infra/var/www/reports/`)
3. Commit et Push depuis `/opt/docs-infra` (`git -C /opt/docs-infra add ...`, `commit`, `push`)
