"""Chemins absolus du projet, calcules a partir de l'emplacement reel du
code (et non codes en dur), pour que chaque instance (production
`/var/www/reports`, dev `/opt/reports-dev`) serve ses propres templates et
fichiers statiques.

Absence de ce module = bug reel trouve le 10 septembre 2026 pendant la
refonte : `ui.py` pointait en dur vers `/var/www/reports/views` et
`/var/www/reports/static`, donc l'interface de dev affichait en realite
les templates et fichiers statiques de production, et sa console SQL
(`/dev`) executait ses requetes sur la base de production (`fetch('/reports/sql')`
code en dur) au lieu de `dt_dev`. Voir NOTES-evolutions.md pour le detail.
"""
from __future__ import annotations

from pathlib import Path

# Ce fichier vit dans <racine>/src/core/paths.py : trois niveaux au-dessus
# se trouve la racine du projet (reports ou reports-dev selon l'instance).
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
WEBDAV_DIR = ROOT_DIR / "webdav"
