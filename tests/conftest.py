"""Configuration pytest partagee : ajoute la racine du projet et src/ au
chemin d'import, fixe un environnement de test coherent (base MariaDB
dt_dev, prefixe /reports-dev) sans dependre de variables deja exportees
par le shell.

A executer avec les memes droits que le process uwsgi reel
(sudo -u mariadb, via ./run_tests.sh), car /etc/boitier-fleet/db-dev.env
n'est lisible que par ce compte. Voir tests/README.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

for path in (str(ROOT_DIR), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

# setdefault : si les tests tournent deja dans un environnement qui les
# fixe autrement (ex. future promotion en production), on ne les ecrase pas.
os.environ.setdefault("REPORTS_BASE_PATH", "/reports-dev")
os.environ.setdefault("DB_ENV_FILE", "/etc/boitier-fleet/db-dev.env")

import pytest


@pytest.fixture(scope="session")
def wsgi_app():
    """L'application WSGI complete (module = app:application, comme la
    voit uwsgi), montee sur REPORTS_BASE_PATH."""
    import app as app_module
    return app_module.application


@pytest.fixture(scope="session")
def base_path():
    import app as app_module
    return app_module.BASE_PATH
