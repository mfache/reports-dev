"""Acces MariaDB. Logique de connexion inchangee par rapport a l'ancien
`db.py` : seule la lecture de configuration a ete deplacee vers
`core.config` (cf. CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import pymysql

from core.config import _ENV


def get_db():
    return pymysql.connect(
        host=_ENV.get("DB_HOST", "localhost"),
        user=_ENV.get("DB_USER", "boitier_app"),
        password=_ENV.get("DB_PASSWORD", ""),
        database=_ENV.get("DB_NAME", "dt"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
