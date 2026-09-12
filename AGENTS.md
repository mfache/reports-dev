# Instructions spécifiques pour le projet reports-dev

Vous êtes dans le bac à sable de développement de l'application `reports`. Le dépôt Git officiel relié à GitHub se trouve dans `/opt/docs-infra/var/www/reports`.

## Règles de développement
- L'interface de dev est accessible via l'application uWSGI `reports-dev`.
- Les modifications de base de données doivent se faire de préférence sur la base `dt_dev`, pas sur la base de production `dt`.

## Flux Git (Important)
Ne faites **jamais** de `git push` directement depuis ce dossier. 

Suivez obligatoirement le flux de travail décrit dans `README-GIT.md` :
1. Commit local dans `/opt/reports-dev`
2. `rsync` vers `/opt/docs-infra/var/www/reports/`
3. Commit et Push depuis `/opt/docs-infra`
