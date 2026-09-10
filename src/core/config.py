"""Configuration centralisee de `reports`.

Isole ce qui etait auparavant duplique/en dur entre `db.py` et `app.py` :
le fichier d'environnement a lire (secrets DB) et le prefixe de montage
WSGI. Sur le modele de `rpinode/src/core/config.py` (voir
CAHIER-DES-CHARGES-REFONTE.md).

Les deux valeurs sont surchargeables via l'environnement uwsgi
(`reports-dev.ini` les fixe a `/etc/boitier-fleet/db-dev.env` et
`/reports-dev` ; `reports.ini`, en production, ne les fixe pas et
conserve donc le comportement historique).
"""
from __future__ import annotations

import os

DB_ENV_FILE = os.environ.get("DB_ENV_FILE", "/etc/boitier-fleet/db.env")

BASE_PATH = os.environ.get("REPORTS_BASE_PATH", "/reports")


def _read_env(path: str) -> dict:
    """Lit un fichier `CLE=valeur` simple (mêmes règles que l'ancien
    `db.py`) : lignes vides et commentaires ignorés, guillemets optionnels
    autour de la valeur. Ne lève jamais si le fichier est absent ou
    illisible (comportement historique conservé)."""
    env: dict[str, str] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


_ENV = _read_env(DB_ENV_FILE)
