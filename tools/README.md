# Outils annexes `reports`

Scripts qui ne font pas partie du code servi en production, rangés par
usage — sur le modèle de `rpinode/tools/`.

- [`migrations/`](migrations/README.md) — scripts de migration ponctuels
  déjà appliqués, conservés comme trace historique. Ne pas rejouer sans
  vérifier au préalable qu'ils ne l'ont pas déjà été.
- `debug/` — scripts de diagnostic ponctuels réutilisables (vide pour
  l'instant : les anciens scripts `test_bottle_*.py`/`test_mount.py`/
  `test_server.py`/`test_uwsgi.py` n'avaient plus de valeur diagnostique
  une fois leur investigation terminée et ont été supprimés plutôt que
  déplacés ici — voir `docs/operations/NOTES-evolutions.md`, 11 septembre
  2026).
- `patches/` — correctifs ponctuels non encore intégrés au code
  principal (vide pour l'instant).

Voir aussi [`../docs/README.md`](../docs/README.md) et
[`../README.md`](../README.md).
