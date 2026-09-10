"""Non-regression du bug trouve le 10 septembre 2026 (soir) : ui.py
pointait en dur vers /var/www/reports/views et /var/www/reports/static,
donc l'interface de dev servait les fichiers de PRODUCTION (voir
NOTES-evolutions.md). core.paths calcule desormais ces chemins depuis
l'emplacement reel du code."""
from __future__ import annotations

from pathlib import Path

from core.paths import ROOT_DIR, STATIC_DIR, VIEWS_DIR


def test_root_dir_correspond_a_ce_checkout():
    # Ce fichier vit dans <racine>/tests/, ROOT_DIR doit donc etre son
    # dossier parent, quel que soit l'endroit ou ce checkout est deploye
    # (/opt/reports-dev en dev, /var/www/reports en prod).
    assert ROOT_DIR == Path(__file__).resolve().parent.parent


def test_views_et_static_dir_existent_dans_ce_checkout():
    assert VIEWS_DIR.is_dir()
    assert STATIC_DIR.is_dir()
    assert (VIEWS_DIR / "layout.tpl").is_file()


def test_aucun_chemin_ne_pointe_vers_var_www_reports_en_dev():
    """Si ce test tourne depuis /opt/reports-dev, aucun des chemins ne
    doit designer le dossier de production."""
    if str(ROOT_DIR) == "/opt/reports-dev":
        assert "/var/www/reports" not in str(VIEWS_DIR)
        assert "/var/www/reports" not in str(STATIC_DIR)
