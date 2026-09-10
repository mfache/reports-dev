# Migrations

Scripts de migration ponctuels, appliqués une fois en production puis
conservés comme trace historique — **ne jamais les rejouer tels quels**
(pas idempotents pour la plupart).

- `20260908_bacnet_aliases_rename.py` / `.sql` / `_schema.sql` —
  renommage de `boitier_annotations` en `boitier_fabricants` et
  création de `chantier_bacnet_aliases` (8 septembre 2026). Déjà
  appliqué : ces tables existent sous leur forme finale en production
  et dans `dt_dev`.

Rangés ici (plutôt qu'à la racine de l'application, où ils vivaient
avant la refonte) pour les séparer clairement du code servi en
production — voir `CAHIER-DES-CHARGES-REFONTE.md` §6.
