"""Raccourcis de chantier envoyés par les boîtiers (/sync, clé ``shortcuts``) :
adresses web d'équipements du LAN du chantier (GTC, automate…), affichées sur
la page « Boîtiers » (web/ui_rpi.py) avec les mêmes droits que les boîtiers.

Le boîtier est la source : la liste qu'il envoie remplace celle qu'il avait
envoyée pour ce chantier. Le lien ouvre l'adresse réelle, routée par
Tailscale (le poste doit avoir Tailscale). Voir rpinode
docs/operations/RACCOURCIS.md.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from core.database import get_db
from services.fleet import log_write

#: Garde-fou : nombre maximal de raccourcis acceptés par chantier et boîtier.
MAX_PAR_ENVOI = 50

_SCHEMA_PRET = False


def assurer_schema():
    """Crée la table au premier usage, sur sa propre connexion (un CREATE
    TABLE valide implicitement la transaction en cours)."""
    global _SCHEMA_PRET
    if _SCHEMA_PRET:
        return
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chantier_raccourcis (
                    id INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
                    chantier_id INT(10) UNSIGNED NOT NULL,
                    libelle VARCHAR(64) NOT NULL,
                    url VARCHAR(255) NOT NULL,
                    updated_by VARCHAR(64) NOT NULL,
                    date_creation TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY idx_chantier (chantier_id),
                    CONSTRAINT fk_chantier_raccourcis_chantier FOREIGN KEY (chantier_id)
                        REFERENCES chantiers(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
                """
            )
    finally:
        db.close()
    _SCHEMA_PRET = True


def url_valide(url: str) -> bool:
    """http(s) vers une IPv4 privée : la seule chose que le boîtier sait router."""
    try:
        parts = urlsplit(url)
        ip = ipaddress.IPv4Address(parts.hostname or "")
        parts.port  # lève ValueError si le port est invalide
    except ValueError:
        return False
    return (parts.scheme in ("http", "https") and ip.is_private
            and not ip.is_loopback and not ip.is_link_local)


def push_raccourcis(cur, boitier_id, chantier_id_resolu, hostname, data):
    """Remplace les raccourcis de ce boîtier pour le chantier qu'il désigne
    (``external_id``, s'il existe sur docs) ou, à défaut, pour le chantier
    résolu par /sync. Les entrées invalides sont ignorées."""
    if not isinstance(data, dict):
        return
    chantier_id = None
    try:
        cur.execute("SELECT id FROM chantiers WHERE id = %s", (int(data.get("external_id")),))
        row = cur.fetchone()
        chantier_id = row["id"] if row else None
    except (TypeError, ValueError):
        pass
    chantier_id = chantier_id or chantier_id_resolu
    if not chantier_id:
        return

    assurer_schema()
    cur.execute("DELETE FROM chantier_raccourcis WHERE chantier_id = %s AND updated_by = %s",
                (chantier_id, hostname[:64]))
    for item in (data.get("items") or [])[:MAX_PAR_ENVOI]:
        if not isinstance(item, dict):
            continue
        libelle = str(item.get("label") or "").strip()[:64]
        url = str(item.get("url") or "").strip()
        if not libelle or len(url) > 255 or not url_valide(url):
            continue
        cur.execute(
            "INSERT INTO chantier_raccourcis (chantier_id, libelle, url, updated_by) VALUES (%s, %s, %s, %s)",
            (chantier_id, libelle, url, hostname[:64]),
        )
    log_write(cur, boitier_id, "chantier_raccourcis", str(chantier_id), "push")


def raccourcis_par_chantier(cur, chantier_ids) -> dict[int, list[dict]]:
    """{chantier_id: [{libelle, url}, …]} pour les chantiers demandés."""
    ids = sorted({int(i) for i in chantier_ids if i})
    if not ids:
        return {}
    assurer_schema()
    cur.execute(
        f"""
        SELECT chantier_id, libelle, url FROM chantier_raccourcis
        WHERE chantier_id IN ({','.join(['%s'] * len(ids))})
        ORDER BY libelle, id
        """,
        ids,
    )
    resultat: dict[int, list[dict]] = {}
    for r in cur.fetchall():
        resultat.setdefault(r["chantier_id"], []).append({"libelle": r["libelle"], "url": r["url"]})
    return resultat
