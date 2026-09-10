"""Resolution/creation automatique de chantier a partir d'une antenne GSM,
et routes de consultation/gestion des chantiers. Extrait d'api.py lors de
la refonte (voir CAHIER-DES-CHARGES-REFONTE.md).

`_resolve_or_create_chantier` est aussi utilise par services/sync.py.
"""
from __future__ import annotations

from bottle import request

from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok
from services.fleet import authenticate_boitier, log_write

_CHANTIER_ANTENNAS_READY = False

def _is_provisional_ref(ref):
    ref = (ref or "").strip()
    return ref.startswith("AUTO-") or ref.startswith("TEMP-")


def _normalize_cell(cell):
    if not cell or not cell.get("mcc") or not cell.get("enodeb"):
        return None
    return (
        str(cell["mcc"])[:8],
        str(cell.get("mnc", ""))[:8],
        str(cell["enodeb"])[:32],
    )


def _ensure_chantier_antennes_schema():
    global _CHANTIER_ANTENNAS_READY
    if _CHANTIER_ANTENNAS_READY:
        return

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chantier_antennes (
                    id INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
                    chantier_id INT(10) UNSIGNED NOT NULL,
                    cell_mcc VARCHAR(8) NOT NULL,
                    cell_mnc VARCHAR(8) NOT NULL DEFAULT '',
                    cell_enodeb VARCHAR(32) NOT NULL,
                    source VARCHAR(32) DEFAULT 'sync',
                    date_creation TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    date_modification TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uniq_chantier_antenne (chantier_id, cell_mcc, cell_mnc, cell_enodeb),
                    KEY idx_antenne_lookup (cell_mcc, cell_mnc, cell_enodeb),
                    CONSTRAINT fk_chantier_antennes_chantier FOREIGN KEY (chantier_id)
                        REFERENCES chantiers(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
                """
            )
            cur.execute(
                """
                INSERT INTO chantier_antennes (chantier_id, cell_mcc, cell_mnc, cell_enodeb, source)
                SELECT id, cell_mcc, COALESCE(cell_mnc, ''), cell_enodeb, 'legacy'
                FROM chantiers
                WHERE cell_mcc IS NOT NULL AND cell_mcc <> ''
                  AND cell_enodeb IS NOT NULL AND cell_enodeb <> ''
                ON DUPLICATE KEY UPDATE source = VALUES(source)
                """
            )
    finally:
        db.close()

def _fetch_chantier_by_id(cur, chantier_id):
    cur.execute("SELECT * FROM chantiers WHERE id=%s LIMIT 1", (chantier_id,))
    return cur.fetchone()


def _fetch_chantier_by_ref(cur, ref):
    ref = (ref or "").strip()[:45]
    if not ref:
        return None
    cur.execute("SELECT * FROM chantiers WHERE ref=%s AND archive=0 LIMIT 1", (ref,))
    return cur.fetchone()


def _link_antenna_to_chantier(cur, chantier_id, mcc, mnc, enodeb, source="sync"):
    cur.execute(
        """
        INSERT INTO chantier_antennes (chantier_id, cell_mcc, cell_mnc, cell_enodeb, source)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            source = VALUES(source),
            date_modification = CURRENT_TIMESTAMP
        """,
        (chantier_id, mcc, mnc, enodeb, source[:32]),
    )
    cur.execute(
        """
        UPDATE chantiers
        SET cell_mcc = COALESCE(NULLIF(cell_mcc, ''), %s),
            cell_mnc = COALESCE(NULLIF(cell_mnc, ''), %s),
            cell_enodeb = COALESCE(NULLIF(cell_enodeb, ''), %s)
        WHERE id = %s
        """,
        (mcc, mnc, enodeb, chantier_id),
    )


def _find_chantiers_by_antenna(cur, mcc, mnc, enodeb):
    cur.execute(
        """
        SELECT c.*
        FROM chantier_antennes ca
        JOIN chantiers c ON c.id = ca.chantier_id
        WHERE ca.cell_mcc=%s AND ca.cell_mnc=%s AND ca.cell_enodeb=%s
          AND c.archive = 0
        ORDER BY CASE
            WHEN c.ref LIKE 'AUTO-%%' OR c.ref LIKE 'TEMP-%%' THEN 1
            ELSE 0
        END,
        c.ref ASC
        """,
        (mcc, mnc, enodeb),
    )
    return cur.fetchall()



def _resolve_or_create_chantier(cur, boitier_id, current_chantier_id, cell, site_hint_name):
    normalized = _normalize_cell(cell)
    if not normalized:
        return None

    _ensure_chantier_antennes_schema()

    mcc, mnc, enodeb = normalized
    ref_hint = (site_hint_name or "").strip()[:45]
    hint_row = _fetch_chantier_by_ref(cur, ref_hint) if ref_hint and not _is_provisional_ref(ref_hint) else None
    candidates = _find_chantiers_by_antenna(cur, mcc, mnc, enodeb)

    if candidates:
        if ref_hint:
            for row in candidates:
                if row["ref"] == ref_hint:
                    return row

        if hint_row and all(_is_provisional_ref(row["ref"]) for row in candidates):
            _link_antenna_to_chantier(cur, hint_row["id"], mcc, mnc, enodeb, source="hint")
            return _fetch_chantier_by_id(cur, hint_row["id"])

        if current_chantier_id is not None:
            try:
                current_chantier_id = int(current_chantier_id)
            except (TypeError, ValueError):
                current_chantier_id = None
            if current_chantier_id is not None:
                for row in candidates:
                    if int(row["id"]) == current_chantier_id:
                        return row

        non_provisional = [row for row in candidates if not _is_provisional_ref(row["ref"])]
        if len(non_provisional) == 1:
            return non_provisional[0]
        if len(candidates) == 1:
            return candidates[0]

        if hint_row:
            _link_antenna_to_chantier(cur, hint_row["id"], mcc, mnc, enodeb, source="hint")
            return _fetch_chantier_by_id(cur, hint_row["id"])

        return non_provisional[0] if non_provisional else candidates[0]

    if hint_row:
        _link_antenna_to_chantier(cur, hint_row["id"], mcc, mnc, enodeb, source="hint")
        return _fetch_chantier_by_id(cur, hint_row["id"])

    ref = ref_hint or f"AUTO-{enodeb}"[:45]
    base_ref = ref
    suffix = 1
    while True:
        cur.execute("SELECT id FROM chantiers WHERE ref=%s", (ref,))
        if not cur.fetchone():
            break
        suffix += 1
        ref = f"{base_ref}-{suffix}"[:45]

    cur.execute(
        "INSERT INTO chantiers (utilisateurs_id, ref, cell_mcc, cell_mnc, cell_enodeb) "
        "VALUES (1, %s, %s, %s, %s)",
        (ref, mcc, mnc, enodeb),
    )
    chantier_id = cur.lastrowid
    _link_antenna_to_chantier(cur, chantier_id, mcc, mnc, enodeb, source="create")
    log_write(cur, boitier_id, "chantiers", ref, "create")
    return _fetch_chantier_by_id(cur, chantier_id)

@api_app.get("/chantier/<chantier_id:int>/net_profiles")
def get_chantier_net_profiles(chantier_id):
    """
    Récupère les profils réseau configurés pour un chantier spécifique.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Usage:
        curl -X GET -H "Authorization: Bearer <token>" https://.../reports/api/chantier/12/net_profiles

    Réponse:
        {
            "ok": true,
            "net_profiles": [...]
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            if not authenticate_boitier(cur):
                return json_error(401, "Jeton invalide ou absent.")

            cur.execute(
                "SELECT name, iface, method, addresses_json, gateway, dhcp_range, wifi_ssid, wifi_psk_encrypted "
                "FROM boitier_net_profiles WHERE chantier_id=%s",
                (chantier_id,)
            )
            net_profiles = []
            for row in cur.fetchall():
                net_profiles.append({
                    "name": row["name"],
                    "iface": row["iface"],
                    "method": row["method"],
                    "addresses": [x.strip() for x in row["addresses_json"].strip("[]").split(",")] if isinstance(row["addresses_json"], str) and row["addresses_json"] else [],
                    "gateway": row["gateway"],
                    "dhcp_range": row["dhcp_range"],
                    "wifi_ssid": row["wifi_ssid"],
                    "psk": row["wifi_psk_encrypted"].decode("utf-8") if row["wifi_psk_encrypted"] else None,
                })

            return json_ok({"ok": True, "net_profiles": net_profiles})
    finally:
        db.close()


@api_app.get("/chantier/<chantier_id:int>/antennes")
def get_chantier_antennes(chantier_id):
    """
    Récupère la liste des antennes GSM associées à un chantier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Usage:
        curl -X GET -H "Authorization: Bearer <token>" https://.../reports/api/chantier/12/antennes

    Réponse:
        {
            "ok": true,
            "antennes": [
                {
                    "mcc": "206",
                    "mnc": "01",
                    "enodeb": "403905",
                    "source": "legacy",
                    "date_modification": "2026-09-07 08:00:00"
                }
            ]
        }
    """
    _ensure_chantier_antennes_schema()
    db = get_db()
    try:
        with db.cursor() as cur:
            if not authenticate_boitier(cur):
                return json_error(401, "Jeton invalide ou absent.")

            cur.execute(
                """
                SELECT cell_mcc AS mcc, cell_mnc AS mnc, cell_enodeb AS enodeb,
                       source, date_creation, date_modification
                FROM chantier_antennes
                WHERE chantier_id=%s
                ORDER BY date_modification DESC, cell_enodeb ASC
                """,
                (chantier_id,)
            )
            return json_ok({"antennes": cur.fetchall()})
    finally:
        db.close()


@api_app.get("/chantiers")
def list_chantiers():
    """
    Récupère la liste de tous les chantiers actifs (non archivés).

    Headers:
        Authorization: Bearer <token_du_boitier>

    Usage:
        curl -X GET -H "Authorization: Bearer <token>" https://.../reports/api/chantiers

    Réponse:
        {
            "ok": true,
            "chantiers": [
                {
                    "id": 1,
                    "ref": "Nom du Chantier",
                    "adresse": "123 Rue de l'Exemple",
                    "antenna_count": 2,
                    "date_modification": "2023-10-25 14:30:00"
                }
            ]
        }
    """
    _ensure_chantier_antennes_schema()
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            cur.execute(
                """
                SELECT c.id, c.ref, c.adresse, c.date_modification,
                       COUNT(ca.id) AS antenna_count
                FROM chantiers c
                LEFT JOIN chantier_antennes ca ON ca.chantier_id = c.id
                WHERE c.archive = 0
                GROUP BY c.id, c.ref, c.adresse, c.date_modification
                ORDER BY c.ref ASC
                """
            )
            chantiers = cur.fetchall()

        return json_ok({"chantiers": chantiers})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()

@api_app.post("/chantier/rename")
def rename_chantier():
    """
    Renomme un chantier existant.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "chantier_id": 12,
            "ref": "Nouveau Nom du Chantier"
        }

    Réponse:
        {
            "ok": true,
            "status": "ok",
            "chantier_id": 12,
            "ref": "Nouveau Nom du Chantier"
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            data = request.json or {}
            new_ref = (data.get("ref") or "").strip()[:45]
            if not new_ref:
                return json_error(400, "Le nouveau nom (ref) est requis.")

            chantier_id = data.get("chantier_id")
            if not chantier_id:
                return json_error(400, "Le paramètre chantier_id est obligatoire.")

            # Vérifier que le nouveau nom n'est pas déjà pris par un autre chantier
            cur.execute("SELECT id FROM chantiers WHERE ref=%s AND id!=%s", (new_ref, chantier_id))
            if cur.fetchone():
                return json_error(409, f"Un chantier avec le nom '{new_ref}' existe déjà.")

            cur.execute("UPDATE chantiers SET ref=%s WHERE id=%s", (new_ref, chantier_id))
            if cur.rowcount == 0:
                # Cela peut arriver si le chantier_id n'existe pas dans la base
                cur.execute("SELECT id FROM chantiers WHERE id=%s", (chantier_id,))
                if not cur.fetchone():
                    return json_error(404, "Chantier introuvable.")

            log_write(cur, boitier["id"], "chantiers", new_ref, "rename")

        return json_ok({"status": "ok", "chantier_id": chantier_id, "ref": new_ref})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()

