import base64
import datetime
import hashlib
import hmac
import json
import gzip
import secrets
import subprocess
import sys

import pymysql
import urllib.error
import urllib.request

from bottle import Bottle, request, response, HTTPResponse
from core.database import get_db
from core.config import _ENV

api_app = Bottle()

import paho.mqtt.publish as mqtt_publish

API_VERSION = "1.2.1"
_CHANTIER_ANTENNAS_READY = False

@api_app.get("/usage")
def global_usage():
    """
    Renvoie la liste des API disponibles et leur usage.
    """
    # Si on appelle directement /reports/api/usage, on n'a pas de "base_path"
    # L'intercepteur va chercher "" ou "/", ce qui n'existe pas ou ne donne pas ce qu'on veut.
    # On gère donc explicitement /reports/api/usage ici.

    import inspect
    import sys

    # On récupère les docstrings de toutes les fonctions enregistrées dans api_app
    api_docs = []
    for route in api_app.routes:
        if route.callback and hasattr(route.callback, '__doc__') and route.callback.__doc__:
            doc = route.callback.__doc__.strip()
            if doc:
                api_docs.append({
                    "method": route.method,
                    "endpoint": route.rule,
                    "usage": doc
                })

    return json_ok({"apis": api_docs})

@api_app.hook('before_request')
def intercept_version_usage():
    """
    Intercepte les requêtes demandant la version ou la documentation de l'API.
    Si l'URL se termine par /version ou /usage, l'API renvoie les infos correspondantes.
    """
    try:
        # Publish an event to the global SSE stream for UI indicators
        mqtt_publish.single("reports/sse/updates", '{"api_activity": true}', hostname="127.0.0.1")
    except Exception:
        pass

    if request.path.endswith("/version"):
        res = HTTPResponse(status=200, body=json_ok({"api_version": API_VERSION}))
        res.content_type = "application/json; charset=utf-8"
        raise res

    if request.path.endswith("/usage"):
        if request.path == "/usage":
            # Ne pas intercepter /usage directement, laisser la route /usage s'en occuper
            return

        base_path = request.path[:-6] # Enlève "/usage"
        doc = None
        for r in api_app.routes:
            if r.rule == base_path or r.rule == base_path + "/":
                doc = r.callback.__doc__
                break

        if doc:
            res = HTTPResponse(status=200, body=json_ok({"usage": doc.strip()}))
            res.content_type = "application/json; charset=utf-8"
            raise res
        else:
            res = HTTPResponse(status=404, body=json_error(404, "Documentation ou endpoint introuvable"))
            res.content_type = "application/json; charset=utf-8"
            raise res

def json_error(status, message):
    response.status = status
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)

def json_ok(payload):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": True, **payload}, ensure_ascii=False, default=str)

def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def check_join_secret():
    expected = _ENV.get("FLEET_JOIN_SECRET", "")
    given = request.headers.get("X-Join-Secret", "")
    return bool(expected) and hmac.compare_digest(expected, given)

def authenticate_boitier(cur):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer ") :].strip()
    if not token:
        return None
    token_hash = hash_token(token)
    cur.execute(
        "SELECT * FROM boitier_registre WHERE token_hash = %s", (token_hash,)
    )
    return cur.fetchone()

def log_write(cur, boitier_id, table_name, record_key, action):
    cur.execute(
        "INSERT INTO boitier_sync_log (boitier_id, table_name, record_key, action) "
        "VALUES (%s, %s, %s, %s)",
        (boitier_id, table_name, record_key, action),
    )

def notify_fleet_change(hostname):
    url = _ENV.get("FLEET_NTFY_URL", "")
    user = _ENV.get("FLEET_NTFY_PUB_USER", "")
    pw = _ENV.get("FLEET_NTFY_PUB_PASS", "")
    if not url or not user:
        return
    try:
        req = urllib.request.Request(
            f"{url}/boitier-fleet-sync",
            data=f"sync:{hostname}".encode("utf-8"),
            method="POST",
        )
        creds = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {creds}")
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"notify_fleet_change: echec (ignore) : {exc}")

@api_app.error(404)
def error404_api(error):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": "Endpoint introuvable (404)"}, ensure_ascii=False)

@api_app.error(500)
def error500_api(error):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": "Erreur interne (500)"}, ensure_ascii=False)

@api_app.get("/ping")
def ping():
    """
    Vérifie la disponibilité de l'API et retourne l'heure serveur.

    Usage:
        curl -X GET https://.../reports/api/ping

    Réponse:
        {
            "ok": true,
            "time": "2023-10-25T14:30:00.123456"
        }
    """
    return json_ok({"time": datetime.datetime.utcnow().isoformat()})

@api_app.post("/register")
def register():
    """
    Enregistre un nouveau boîtier sur le serveur central.

    Headers:
        X-Join-Secret: <Le secret d'adhésion de la flotte>

    Payload:
        {
            "hostname": "DT-12345",
            "tailscale_name": "dt-12345.tailnet.ts.net"
        }

    Réponse:
        {
            "ok": true,
            "token": "secret_token_genere_par_le_serveur"
        }
    """
    if not check_join_secret():
        return json_error(403, "Secret d'adhesion invalide ou absent.")
    data = request.json or {}
    hostname = (data.get("hostname") or "").strip()
    tailscale_name = (data.get("tailscale_name") or "").strip()
    if not hostname:
        return json_error(400, "hostname requis.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM boitier_registre WHERE hostname = %s", (hostname,)
            )
            existing = cur.fetchone()
            if existing:
                return json_error(
                    409,
                    "Ce boitier est deja enregistre (jeton deja emis, non "
                    "recuperable). Supprimez son enregistrement cote serveur "
                    "avant de le re-enregistrer.",
                )
            token = secrets.token_urlsafe(32)
            cur.execute(
                "INSERT INTO boitier_registre (hostname, tailscale_name, token_hash) "
                "VALUES (%s, %s, %s)",
                (hostname, tailscale_name, hash_token(token)),
            )
            boitier_id = cur.lastrowid
            log_write(cur, boitier_id, "boitier_registre", hostname, "register")
        return json_ok({"token": token})
    finally:
        db.close()

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

    _CHANTIER_ANTENNAS_READY = True


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
def _push_net_profiles(cur, boitier_id, chantier_id, hostname, profiles):
    cur.execute("DELETE FROM boitier_net_profiles WHERE chantier_id=%s AND updated_by=%s", (chantier_id, hostname[:64]))
    for p in profiles or []:
        name = (p.get("name") or "").strip()[:64]
        if not name:
            continue
        cur.execute(
            """INSERT INTO boitier_net_profiles
                 (chantier_id, name, iface, method, addresses_json,
                  wifi_ssid, wifi_psk_encrypted, updated_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                 iface=VALUES(iface), method=VALUES(method),
                 addresses_json=VALUES(addresses_json),
                 wifi_ssid=VALUES(wifi_ssid),
                 wifi_psk_encrypted=VALUES(wifi_psk_encrypted),
                 updated_by=VALUES(updated_by)""",
            (
                chantier_id,
                name,
                (p.get("iface") or "")[:16],
                (p.get("method") or "")[:16],
                json.dumps(p.get("addresses") or [], ensure_ascii=False),
                (p.get("wifi_ssid") or None),
                (p.get("wifi_psk") or None),
                hostname[:64],
            ),
        )
        log_write(cur, boitier_id, "boitier_net_profiles", name, "push")

def _push_modbus_templates(cur, boitier_id, boitier_hostname, templates):
    import uuid
    items = []
    if isinstance(templates, dict):
        for k, v in templates.items():
            if isinstance(v, dict):
                v_copy = dict(v)
                if "name" not in v_copy and "template_uuid" not in v_copy:
                    v_copy["name"] = str(k)
                items.append(v_copy)
            else:
                items.append({"name": str(k), "definition": v})
    elif isinstance(templates, list):
        items = templates

    for item in items:
        name = str(item.get("name") or "").strip()[:128]
        if not name and isinstance(item.get("definition"), dict):
            name = str(item["definition"].get("name") or "").strip()[:128]
        if not name:
            continue

        tpl_uuid = item.get("template_uuid")
        if not tpl_uuid:
            cur.execute("SELECT template_uuid FROM boitier_modbus_templates WHERE name=%s ORDER BY id ASC LIMIT 1", (name,))
            existing_t = cur.fetchone()
            if existing_t:
                tpl_uuid = existing_t["template_uuid"]
            else:
                tpl_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"template-{name}"))
        tpl_uuid = str(tpl_uuid)[:64]

        rev_uuid = item.get("revision_uuid")
        if not rev_uuid:
            rev_uuid = str(uuid.uuid4())
        rev_uuid = str(rev_uuid)[:64]

        parent_rev_uuid = item.get("parent_revision_uuid")
        if parent_rev_uuid:
            parent_rev_uuid = str(parent_rev_uuid)[:64]

        manufacturer = item.get("manufacturer") or item.get("notes")
        if not manufacturer and isinstance(item.get("definition"), dict):
            manufacturer = item["definition"].get("notes") or item["definition"].get("manufacturer")
        manufacturer = str(manufacturer)[:128] if manufacturer else None

        version = int(item.get("version") or 1)
        node_name = str(item.get("created_by_node") or boitier_hostname or "rpi01")[:64]
        is_deprecated = 1 if item.get("is_deprecated") else 0

        if "definition" in item and isinstance(item["definition"], (dict, list)):
            def_dict = item["definition"]
        elif "reads" in item or "port" in item:
            def_dict = {
                "name": name,
                "notes": manufacturer or "",
                "port": item.get("port", 502),
                "unit": item.get("unit", 1),
                "base": item.get("base", 0),
                "reads": item.get("reads", []),
                "commands": item.get("commands", [])
            }
        else:
            def_dict = item

        definition_json = json.dumps(def_dict, ensure_ascii=False)

        cur.execute("SELECT id FROM boitier_modbus_templates WHERE revision_uuid=%s", (rev_uuid,))
        existing_rev = cur.fetchone()
        if existing_rev:
            cur.execute(
                """UPDATE boitier_modbus_templates
                   SET name=%s, manufacturer=%s, version=%s, definition_json=%s, is_deprecated=%s
                   WHERE revision_uuid=%s""",
                (name, manufacturer, version, definition_json, is_deprecated, rev_uuid),
            )
        else:
            cur.execute(
                """INSERT INTO boitier_modbus_templates
                   (template_uuid, revision_uuid, parent_revision_uuid, name, manufacturer, version, definition_json, created_by_node, is_deprecated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (tpl_uuid, rev_uuid, parent_rev_uuid, name, manufacturer, version, definition_json, node_name, is_deprecated),
            )
        log_write(cur, boitier_id, "boitier_modbus_templates", f"{name}:{rev_uuid}", "push")

def _push_bacnet_templates(cur, boitier_id, boitier_hostname, templates):
    import uuid
    items = []
    if isinstance(templates, dict):
        for k, v in templates.items():
            if isinstance(v, dict):
                v_copy = dict(v)
                if "name" not in v_copy and "template_uuid" not in v_copy:
                    v_copy["name"] = str(k)
                items.append(v_copy)
            else:
                items.append({"name": str(k), "definition": v})
    elif isinstance(templates, list):
        items = templates

    for item in items:
        name = str(item.get("name") or "").strip()[:128]
        if not name and isinstance(item.get("definition"), dict):
            name = str(item["definition"].get("name") or "").strip()[:128]
        if not name:
            continue

        tpl_uuid = item.get("template_uuid")
        if not tpl_uuid:
            cur.execute("SELECT template_uuid FROM boitier_bacnet_templates WHERE name=%s ORDER BY id ASC LIMIT 1", (name,))
            existing_t = cur.fetchone()
            if existing_t:
                tpl_uuid = existing_t["template_uuid"]
            else:
                tpl_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bacnet-template-{name}"))
        tpl_uuid = str(tpl_uuid)[:64]

        rev_uuid = item.get("revision_uuid")
        if not rev_uuid:
            rev_uuid = str(uuid.uuid4())
        rev_uuid = str(rev_uuid)[:64]

        parent_rev_uuid = item.get("parent_revision_uuid")
        if parent_rev_uuid:
            parent_rev_uuid = str(parent_rev_uuid)[:64]

        manufacturer = item.get("manufacturer") or item.get("notes")
        if not manufacturer and isinstance(item.get("definition"), dict):
            manufacturer = item["definition"].get("notes") or item["definition"].get("manufacturer")
        manufacturer = str(manufacturer)[:128] if manufacturer else None

        version = int(item.get("version") or 1)
        node_name = str(item.get("created_by_node") or boitier_hostname or "rpi01")[:64]
        is_deprecated = 1 if item.get("is_deprecated") else 0

        if "definition" in item and isinstance(item["definition"], (dict, list)):
            def_dict = item["definition"]
        elif "objects" in item:
            def_dict = {
                "name": name,
                "notes": manufacturer or "",
                "objects": item.get("objects", [])
            }
        else:
            def_dict = item

        definition_json = json.dumps(def_dict, ensure_ascii=False)

        cur.execute("SELECT id FROM boitier_bacnet_templates WHERE revision_uuid=%s", (rev_uuid,))
        existing_rev = cur.fetchone()
        if existing_rev:
            cur.execute(
                """UPDATE boitier_bacnet_templates
                   SET name=%s, manufacturer=%s, version=%s, definition_json=%s, is_deprecated=%s
                   WHERE revision_uuid=%s""",
                (name, manufacturer, version, definition_json, is_deprecated, rev_uuid),
            )
        else:
            cur.execute(
                """INSERT INTO boitier_bacnet_templates
                   (template_uuid, revision_uuid, parent_revision_uuid, name, manufacturer, version, definition_json, created_by_node, is_deprecated)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (tpl_uuid, rev_uuid, parent_rev_uuid, name, manufacturer, version, definition_json, node_name, is_deprecated),
            )
        log_write(cur, boitier_id, "boitier_bacnet_templates", f"{name}:{rev_uuid}", "push")

def _push_template_usage(cur, boitier_id, boitier_hostname, default_chantier_id, usages):
    cur.execute("DELETE FROM boitier_template_usage WHERE boitier_id=%s", (boitier_hostname,))
    for u in usages or []:
        tpl_uuid = str(u.get("template_uuid") or "")[:64]
        rev_uuid = str(u.get("revision_uuid") or "")[:64]
        dev_name = str(u.get("device_name") or "")[:128]
        c_id = u.get("chantier_id") if u.get("chantier_id") is not None else default_chantier_id
        try:
            c_id = int(c_id or 0)
        except (ValueError, TypeError):
            c_id = 0

        if not tpl_uuid or not rev_uuid or not dev_name:
            continue

        cur.execute(
            """INSERT INTO boitier_template_usage
               (boitier_id, chantier_id, template_uuid, revision_uuid, device_name, last_reported_at)
               VALUES (%s, %s, %s, %s, %s, NOW())
               ON DUPLICATE KEY UPDATE revision_uuid=VALUES(revision_uuid), last_reported_at=NOW()""",
            (boitier_hostname, c_id, tpl_uuid, rev_uuid, dev_name),
        )
    log_write(cur, boitier_id, "boitier_template_usage", boitier_hostname, "push")

def _push_annotations(cur, boitier_id, chantier_id, annotations):
    for a in annotations or []:
        kind = (a.get("kind") or "")[:16]
        entry_key = (a.get("key") or "")[:128]
        field = (a.get("field") or "")[:64]
        value = a.get("value")
        if not kind or not entry_key:
            continue

        if kind.startswith("bacnet") and chantier_id and field in ("alias", "_alias", "name", "label"):
            cur.execute(
                """INSERT INTO chantier_bacnet_aliases (chantier_id, device_instance, alias, updated_by)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE alias=VALUES(alias), updated_by=VALUES(updated_by)""",
                (chantier_id, entry_key, value, request.json.get("hostname", "")[:64]),
            )
            log_write(cur, boitier_id, "chantier_bacnet_aliases", f"{chantier_id}:{entry_key}", "push")
        else:
            cur.execute(
                """INSERT INTO boitier_fabricants (kind, entry_key, field, value, updated_by)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE value=VALUES(value), updated_by=VALUES(updated_by)""",
                (kind, entry_key, field, value, request.json.get("hostname", "")[:64]),
            )
            log_write(cur, boitier_id, "boitier_fabricants", f"{kind}:{entry_key}:{field}", "push")


def _push_table_columns(cur, boitier_id, columns):
    for col in columns or []:
        table_id = (col.get("table_id") or "")[:32]
        column_key = (col.get("column_key") or "")[:64]
        column_label = (col.get("column_label") or "")[:128]
        if not table_id or not column_key:
            continue
        cur.execute(
            """INSERT INTO boitier_table_columns (table_id, column_key, column_label, updated_by)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                 column_label=VALUES(column_label),
                 updated_by=VALUES(updated_by)""",
            (table_id, column_key, column_label, request.json.get("hostname", "")[:64]),
        )
        log_write(cur, boitier_id, "boitier_table_columns", f"{table_id}:{column_key}", "push")

def _push_bacnet_points_catalog(cur, boitier_id, hostname, points):
    """
    Persiste le dictionnaire de points BACnet decouverts par un boitier. Chaque point
    porte son propre chantier_id (le boitier peut avoir change de chantier entre deux
    lots), donc on ne retombe jamais sur le chantier_id du contexte de la requete.
    """
    for p in points or []:
        chantier_id = p.get("chantier_id")
        device_instance = p.get("device_instance")
        object_id = (p.get("object_id") or "")[:64]
        if not chantier_id or device_instance is None or not object_id:
            continue
        network_address = (p.get("network_address") or "")[:64]
        object_name = (p.get("object_name") or "")[:255]
        cur.execute(
            """INSERT INTO chantier_bacnet_points
                   (chantier_id, network_address, device_instance, object_id, object_name, updated_by)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                 network_address=VALUES(network_address),
                 object_name=VALUES(object_name),
                 updated_by=VALUES(updated_by)""",
            (chantier_id, network_address, device_instance, object_id, object_name, hostname[:64] if hostname else ""),
        )
    if points:
        log_write(cur, boitier_id, "chantier_bacnet_points", f"batch:{len(points)}", "push")

@api_app.post("/sync")
def sync():
    """
    Synchronise la configuration et récupère les instructions du serveur.
    Peut pousser de nouveaux profils réseau, templates Modbus ou annotations vers le serveur.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload (optionnel):
        {
            "cell": {"mcc": 208, "mnc": 10, "enodeb": "123456"},
            "site_hint_name": "Nom Site",
            "net_profiles": [...],
            "modbus_templates": {...},
            "annotations": [...]
        }

    Notes:
        - Un chantier peut être associé à plusieurs antennes GSM (eNodeB).
        - Le serveur privilégie d'abord une correspondance exacte par antenne.
        - Si l'antenne est nouvelle mais que ``site_hint_name`` désigne un chantier
          existant, l'antenne est rattachée à ce chantier au lieu de créer un doublon
          du type ``Nom Site-2``.
        - Le payload peut aussi être compressé en GZIP via ``Content-Encoding: gzip``.

    Réponse:
        {
            "ok": true,
            "chantier": {"id": 12, "ref": "Nom Site"},
            "net_profiles": [...],
            "modbus_templates": {...},
            "annotations": [...]
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            if request.headers.get('Content-Encoding') == 'gzip':
                try:
                    data = json.loads(gzip.decompress(request.body.read()).decode('utf-8'))
                except Exception:
                    return json_error(400, "Erreur de décompression GZIP")
            else:
                data = request.json or {}
            boitier_id = boitier["id"]

            chantier = _resolve_or_create_chantier(
                cur, boitier_id, boitier.get("chantier_id"), data.get("cell"), data.get("site_hint_name")
            )
            chantier_id = chantier["id"] if chantier else boitier.get("chantier_id")

            pushed_something = False
            handlers = [
                ("net_profiles", _push_net_profiles, [cur, boitier_id, chantier_id, boitier["hostname"]]),
                ("modbus_templates", _push_modbus_templates, [cur, boitier_id, boitier["hostname"]]),
                ("template_usage", _push_template_usage, [cur, boitier_id, boitier["hostname"], chantier_id]),
                ("annotations", _push_annotations, [cur, boitier_id, chantier_id]),
                ("table_columns", _push_table_columns, [cur, boitier_id]),
                ("bacnet_points_catalog", _push_bacnet_points_catalog, [cur, boitier_id, boitier["hostname"]]),
                ("bacnet_templates", _push_bacnet_templates, [cur, boitier_id, boitier["hostname"]]),
            ]

            for key, func, args in handlers:
                # Pour les profils réseau, on exige en plus que chantier_id soit défini
                if key in data and (key != "net_profiles" or chantier_id):
                    func(*args, data[key])
                    pushed_something = True

            cur.execute(
                "UPDATE boitier_registre SET last_sync_at=NOW(), last_ip=%s, "
                "tailscale_name=%s, chantier_id=%s WHERE id=%s",
                (
                    request.remote_addr,
                    data.get("tailscale_name", boitier.get("tailscale_name")),
                    chantier_id,
                    boitier_id,
                ),
            )

            net_profiles = []
            if chantier_id:
                cur.execute(
                    "SELECT name, iface, method, addresses_json, gateway, dhcp_range, wifi_ssid, wifi_psk_encrypted "
                    "FROM boitier_net_profiles WHERE chantier_id=%s",
                    (chantier_id,),
                )
                for row in cur.fetchall():
                    net_profiles.append(
                        {
                            "name": row["name"],
                            "iface": row["iface"],
                            "method": row["method"],
                            "addresses": [x.strip() for x in row["addresses_json"].strip("[]").split(",")] if isinstance(row["addresses_json"], str) and row["addresses_json"] else [],
                            "gateway": row["gateway"],
                            "dhcp_range": row["dhcp_range"],
                            "wifi_ssid": row["wifi_ssid"],
                            "psk": row["wifi_psk_encrypted"].decode("utf-8") if row["wifi_psk_encrypted"] else None,
                        }
                    )

            cur.execute("""
                SELECT t1.id, t1.template_uuid, t1.revision_uuid, t1.parent_revision_uuid,
                       t1.name, t1.manufacturer, t1.version, t1.definition_json,
                       t1.created_by_node, t1.is_deprecated, t1.date_creation, t1.date_modification
                FROM boitier_modbus_templates t1
                INNER JOIN (
                    SELECT template_uuid, MAX(version) as max_version, MAX(id) as max_id
                    FROM boitier_modbus_templates
                    WHERE is_deprecated = 0
                    GROUP BY template_uuid
                ) t2 ON t1.template_uuid = t2.template_uuid AND t1.version = t2.max_version AND t1.id = t2.max_id
                ORDER BY t1.name ASC
            """)
            modbus_templates = {}
            for row in cur.fetchall():
                try:
                    defn = json.loads(row["definition_json"])
                except Exception:
                    defn = {}
                defn["template_uuid"] = row["template_uuid"]
                defn["revision_uuid"] = row["revision_uuid"]
                defn["parent_revision_uuid"] = row["parent_revision_uuid"]
                defn["name"] = row["name"]
                defn["manufacturer"] = row["manufacturer"] or defn.get("notes", "")
                defn["notes"] = row["manufacturer"] or defn.get("notes", "")
                defn["version"] = row["version"]
                defn["created_by_node"] = row["created_by_node"]
                defn["is_deprecated"] = bool(row["is_deprecated"])
                modbus_templates[row["name"]] = defn

            cur.execute("""
                SELECT t1.id, t1.template_uuid, t1.revision_uuid, t1.parent_revision_uuid,
                       t1.name, t1.manufacturer, t1.version, t1.definition_json,
                       t1.created_by_node, t1.is_deprecated, t1.date_creation, t1.date_modification
                FROM boitier_bacnet_templates t1
                INNER JOIN (
                    SELECT template_uuid, MAX(version) as max_version, MAX(id) as max_id
                    FROM boitier_bacnet_templates
                    WHERE is_deprecated = 0
                    GROUP BY template_uuid
                ) t2 ON t1.template_uuid = t2.template_uuid AND t1.version = t2.max_version AND t1.id = t2.max_id
                ORDER BY t1.name ASC
            """)
            bacnet_templates = {}
            for row in cur.fetchall():
                try:
                    defn = json.loads(row["definition_json"])
                except Exception:
                    defn = {}
                defn["template_uuid"] = row["template_uuid"]
                defn["revision_uuid"] = row["revision_uuid"]
                defn["parent_revision_uuid"] = row["parent_revision_uuid"]
                defn["name"] = row["name"]
                defn["manufacturer"] = row["manufacturer"] or defn.get("notes", "")
                defn["notes"] = row["manufacturer"] or defn.get("notes", "")
                defn["version"] = row["version"]
                defn["created_by_node"] = row["created_by_node"]
                defn["is_deprecated"] = bool(row["is_deprecated"])
                bacnet_templates[row["name"]] = defn

            cur.execute("SELECT kind, entry_key, field, value FROM boitier_fabricants")
            annotations = [
                {
                    "kind": row["kind"],
                    "key": row["entry_key"],
                    "field": row["field"],
                    "value": row["value"],
                }
                for row in cur.fetchall()
            ]

            cur.execute("SELECT table_id, column_key, column_label FROM boitier_table_columns")
            table_columns = [
                {
                    "table_id": row["table_id"],
                    "column_key": row["column_key"],
                    "column_label": row["column_label"],
                }
                for row in cur.fetchall()
            ]

            if chantier_id:
                cur.execute("SELECT device_instance, alias FROM chantier_bacnet_aliases WHERE chantier_id=%s", (chantier_id,))
                for row in cur.fetchall():
                    annotations.append({
                        "kind": "bacnet_device",
                        "key": row["device_instance"],
                        "field": "_alias",
                        "value": row["alias"]
                    })

        if pushed_something:
            notify_fleet_change(data.get("hostname", "?"))

        return json_ok(
            {
                "chantier": (
                    {"id": chantier["id"], "ref": chantier["ref"]} if chantier else None
                ),
                "net_profiles": net_profiles,
                "modbus_templates": modbus_templates,
                "bacnet_templates": bacnet_templates,
                "annotations": annotations,
                "table_columns": table_columns,
            }
        )
    finally:
        db.close()


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

@api_app.post("/trends")
def trends():
    """
    Envoie des relevés historiques (trends) de capteurs.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "trends": [
                {
                    "s": "ID_site",
                    "p": "bacnet",
                    "t": 1698240000,
                    "d": "1234",
                    "o": "AI:1",
                    "v": "23.5"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "status": "ok",
            "received": 1,
            "inserted": 1
        }
    """
    # Ouverture de la connexion à la base de données
    db = get_db()
    try:
        with db.cursor() as cur:
            # Authentification du boîtier via son jeton pour vérifier ses droits d'accès
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            # Récupération de la charge utile JSON envoyée par le boîtier
            data = request.json or {}
            trends_data = data.get("trends", [])

            # S'il n'y a aucune donnée à traiter, on retourne immédiatement un succès
            if not trends_data:
                return json_ok({"status": "ok", "received": 0, "inserted": 0})

            # L'identifiant (hostname) du boîtier qui servira de référence pour chaque ligne
            boitier_id = boitier["hostname"]

            # Préparation des enregistrements pour une insertion groupée (batch)
            values = []
            for t in trends_data:
                # Vérification de la présence de tous les champs obligatoires :
                # p: protocole, t: timestamp, d: device, o: object, v: value
                if "p" not in t or "t" not in t or "d" not in t or "o" not in t or "v" not in t:
                    continue

                # Conversion des types et troncature des chaînes de caractères aux limites
                # des colonnes en base pour éviter des erreurs SQL de débordement
                values.append((
                    boitier_id,
                    str(t.get("s", ""))[:128],  # Site (champ optionnel, par défaut vide)
                    str(t["p"])[:32],           # Protocole (ex: bacnet, modbus...)
                    int(t["t"]),                # Horodatage (epoch)
                    str(t["d"])[:128],          # Équipement / Périphérique (device)
                    str(t["o"])[:128],          # Identifiant du point de mesure (object)
                    str(t["v"])[:255]           # Valeur relevée (stockée sous forme de chaîne)
                ))


                # try:
                #     payload = {
                #         # Ajout du préfixe sse_ pour l'injection auto
                #         "tmp_value": str(t["v"])[:255]
                #     }
                #     mqtt_publish.single(
                #         "reports/sse/updates",
                #         json.dumps(payload), # Garantit un JSON parfaitement valide
                #         hostname="127.0.0.1"
                #     )
                # except Exception:
                #     pass

            # Si toutes les données ont été ignorées (invalides), on arrête là
            if not values:
                return json_ok({"status": "ok", "received": len(trends_data), "inserted": 0})

            # Insertion en base de données. L'utilisation de INSERT IGNORE permet
            # d'ignorer silencieusement les doublons (si le boîtier renvoie une donnée déjà reçue)
            cur.executemany(
                "INSERT IGNORE INTO boitier_trends (boitier_id, site, protocol, timestamp, device, obj, value) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                values
            )
            # rowcount donne le nombre de lignes réellement insérées (hors doublons)
            inserted = cur.rowcount

        # Succès : on renvoie au boîtier le bilan des données traitées
        return json_ok({"status": "ok", "received": len(trends_data), "inserted": inserted})
    except Exception as e:
        # En cas d'erreur inattendue (ex: base de données injoignable), on retourne un code 500
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        # Assure la libération du pool / fermeture de la connexion DB systématiquement
        db.close()

@api_app.post("/points-config")
def points_config():
    """
    Envoie ou met à jour la configuration des points scannés par le boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "points": [
                {
                    "s": "ID_site",
                    "p": "bacnet",
                    "d": "1234",
                    "o": "AI:1",
                    "label": "Température Ambiante"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "status": "ok",
            "updated": 1
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            data = request.json or {}
            points_data = data.get("points", [])

            if not points_data:
                return json_ok({"status": "ok", "updated": 0})

            boitier_id = boitier["hostname"]

            values = []
            for p in points_data:
                if "p" not in p or "d" not in p or "o" not in p:
                    continue
                values.append((boitier_id, str(p.get("s", ""))[:128], str(p["p"])[:32], str(p["d"])[:128], str(p["o"])[:128], p.get("label")))

            if not values:
                return json_ok({"status": "ok", "updated": 0})

            cur.executemany(
                "INSERT INTO boitier_points_config (boitier_id, site, protocol, device, obj, label) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE label = VALUES(label)",
                values
            )
            updated = cur.rowcount

        return json_ok({"status": "ok", "updated": updated})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()

@api_app.post("/logs")
def post_logs():
    """
    Enregistre des logs envoyés par un boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "logs": [
                {
                    "level": "ERROR",
                    "module": "services.tracker",
                    "message": "Erreur SQL",
                    "timestamp": "2023-10-25T14:30:00"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "inserted": 1
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            if request.headers.get('Content-Encoding') == 'gzip':
                try:
                    data = json.loads(gzip.decompress(request.body.read()).decode('utf-8'))
                except Exception:
                    return json_error(400, "Erreur de décompression GZIP")
            else:
                data = request.json or {}
            logs = data.get("logs", [])
            if not logs:
                return json_ok({"inserted": 0})

            inserted = 0
            for log_entry in logs:
                level = str(log_entry.get("level", "INFO"))[:16]
                module = str(log_entry.get("module", "unknown"))[:128]
                message = str(log_entry.get("message", ""))
                timestamp = log_entry.get("timestamp")
                git_version = str(log_entry.get("git_version", ""))[:64]
                chantier_id = boitier.get("chantier_id")

                if not timestamp:
                    timestamp = datetime.datetime.utcnow().isoformat()

                cur.execute(
                    "INSERT INTO boitier_logs (boitier_id, chantier_id, level, module, message, timestamp, git_version) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (boitier["id"], chantier_id, level, module, message, timestamp, git_version)
                )
                inserted += 1

        return json_ok({"inserted": inserted})
    finally:
        db.close()

@api_app.get("/logs")
def get_logs():
    """
    Récupère les derniers logs enregistrés par le boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Query params optionnels:
        limit: Nombre de logs à retourner (défaut 50)
        level: Filtrer par niveau (ex: ERROR)

    Réponse:
        {
            "ok": true,
            "logs": [...]
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            limit = int(request.query.get("limit", 50))
            level = request.query.get("level")

            query = "SELECT * FROM boitier_logs WHERE boitier_id = %s"
            params = [boitier["id"]]

            if level:
                query += " AND level = %s"
                params.append(level)

            query += " ORDER BY id DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return json_ok({"logs": rows})
    finally:
        db.close()

@api_app.post("/table/column/delete")
def delete_table_column():
    """
    Supprime une définition de colonne personnalisée.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            data = request.json or {}
            table_id = data.get("table_id")
            column_key = data.get("column_key")

            if not table_id or not column_key:
                return json_error(400, "Données manquantes")

            cur.execute(
                "DELETE FROM boitier_table_columns WHERE table_id=%s AND column_key=%s",
                (table_id, column_key)
            )
            log_write(cur, boitier["id"], "boitier_table_columns", f"{table_id}:{column_key}", "delete")

        notify_fleet_change(data.get("hostname", "?"))
        return json_ok({"status": "ok"})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Auto-enrolement des boitiers (hostname assigne par le serveur) et
# integration Headscale (voir rpinode: docs/integrations/HEADSCALE_AUTO_ENROLL.md)
# Ajoute le 8 septembre 2026.
# ---------------------------------------------------------------------------

HEADSCALE_BIN = "headscale"
HEADSCALE_USER_ID = "1"  # utilisateur Headscale "delta"
HEADSCALE_LOGIN_SERVER = "https://docs.deltathermic.be"
HEADSCALE_FLEET_TAG = "tag:fleet"  # pose automatiquement sur chaque noeud boitier


def _next_rpi_hostname(cur):
    """Calcule le prochain nom d'hote 'rpiNN' libre (NN croissant, jamais reutilise)."""
    cur.execute(
        "SELECT hostname FROM boitier_registre WHERE hostname REGEXP '^rpi[0-9]+$'"
    )
    max_n = 0
    for row in cur.fetchall():
        try:
            n = int(row["hostname"][3:])
            max_n = max(max_n, n)
        except (ValueError, KeyError, TypeError):
            continue
    return f"rpi{max_n + 1:02d}"


@api_app.post("/register/auto")
def register_auto():
    """
    Enregistre un nouveau boitier en lui attribuant automatiquement un nom
    d'hote (rpiNN), a partir de son identifiant materiel unique (numero de
    serie CPU du Raspberry Pi).

    Headers:
        X-Join-Secret: <Le secret d'adhesion de la flotte>

    Payload:
        {
            "cpu_serial": "100000004d559626"
        }

    Reponse:
        {
            "ok": true,
            "token": "secret_token_genere_par_le_serveur",
            "hostname": "rpi02"
        }

    Si un boitier avec ce cpu_serial est deja connu (reinstallation d'une
    carte SD par exemple), son jeton est regenere (l'ancien devient invalide)
    mais il conserve le meme nom d'hote.
    """
    if not check_join_secret():
        return json_error(403, "Secret d'adhesion invalide ou absent.")
    data = request.json or {}
    cpu_serial = (data.get("cpu_serial") or "").strip()
    if not cpu_serial:
        return json_error(400, "cpu_serial requis.")

    token = secrets.token_urlsafe(32)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, hostname FROM boitier_registre WHERE cpu_serial = %s",
                (cpu_serial,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE boitier_registre SET token_hash = %s WHERE id = %s",
                    (hash_token(token), existing["id"]),
                )
                hostname = existing["hostname"]
                log_write(cur, existing["id"], "boitier_registre", hostname, "re-register")
                return json_ok({"token": token, "hostname": hostname})

            # Nouveau boitier : on attribue le prochain nom "rpiNN" libre. On
            # boucle en cas de collision improbable (concurrence entre deux
            # enregistrements simultanes).
            for _ in range(5):
                hostname = _next_rpi_hostname(cur)
                try:
                    cur.execute(
                        "INSERT INTO boitier_registre (hostname, cpu_serial, token_hash) "
                        "VALUES (%s, %s, %s)",
                        (hostname, cpu_serial, hash_token(token)),
                    )
                    boitier_id = cur.lastrowid
                    log_write(cur, boitier_id, "boitier_registre", hostname, "register-auto")
                    return json_ok({"token": token, "hostname": hostname})
                except pymysql.err.IntegrityError:
                    continue
            return json_error(500, "Impossible d'attribuer un nom d'hote (collisions repetees).")
    finally:
        db.close()


def _run_headscale(args, want_json=True):
    """Execute `headscale <args>` (+ -o json) et renvoie la sortie parsee.
    Leve RuntimeError avec le message d'erreur du CLI en cas d'echec."""
    cmd = [HEADSCALE_BIN] + list(args)
    if want_json:
        cmd = cmd + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "echec headscale inconnu")
    out = result.stdout.strip()
    if not want_json:
        return out
    return json.loads(out) if out else []


def _find_headscale_node(hostname):
    nodes = _run_headscale(["nodes", "list"])
    for n in nodes:
        if n.get("name") == hostname or n.get("given_name") == hostname:
            return n
    return None


def _ensure_fleet_tag(node):
    """Pose le tag tag:fleet sur le noeud s'il ne l'a pas deja. Idempotent,
    sans effet si deja present. Les erreurs sont journalisees mais ne font
    pas echouer l'appelant (le taggage est secondaire par rapport a
    l'approbation des routes)."""
    if HEADSCALE_FLEET_TAG in (node.get("tags") or []):
        return
    try:
        _run_headscale(
            ["nodes", "tag", "--identifier", str(node["id"]), "--tags", HEADSCALE_FLEET_TAG],
            want_json=False,
        )
    except Exception as exc:
        print(f"[headscale] echec du taggage {HEADSCALE_FLEET_TAG} sur le noeud {node.get('id')}: {exc}", file=sys.stderr)


@api_app.post("/headscale/enroll")
def headscale_enroll():
    """
    Genere une cle de pre-authentification Headscale a usage unique pour le
    boitier authentifie (identifie par son hostname assigne), et supprime au
    prealable un eventuel ancien noeud Headscale portant le meme nom
    (cas d'une carte SD reinstallee).

    Headers:
        Authorization: Bearer <jeton_flotte>

    Payload (optionnel):
        {
            "advertise_routes": ["10.42.0.0/24", "192.168.1.0/24"]
        }

    Reponse:
        {
            "ok": true,
            "authkey": "...",
            "hostname": "rpi02",
            "login_server": "https://docs.deltathermic.be"
        }

    La cle generee ne concerne que l'authentification initiale : les routes
    annoncees sont approuvees separement (et a chaque changement) via
    POST /headscale/routes, appele par le boitier apres chaque
    `tailscale set --advertise-routes=...` (donc a chaque changement de
    chantier), pas seulement lors de cet enrolement initial.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")
            hostname = boitier["hostname"]

            try:
                existing_node = _find_headscale_node(hostname)
                if existing_node:
                    _run_headscale(
                        ["nodes", "delete", "--identifier", str(existing_node["id"]), "--force"],
                        want_json=False,
                    )
                key_data = _run_headscale(
                    [
                        "preauthkeys", "create",
                        "--user", HEADSCALE_USER_ID,
                        "--expiration", "5m",
                        "--reusable=false",
                    ]
                )
                authkey = key_data.get("key") if isinstance(key_data, dict) else None
                if not authkey:
                    return json_error(500, "Impossible de generer la cle Headscale.")
            except Exception as exc:
                return json_error(500, f"Erreur Headscale : {exc}")

            log_write(cur, boitier["id"], "boitier_registre", hostname, "hs-enroll")

        return json_ok({
            "authkey": authkey,
            "hostname": hostname,
            "login_server": HEADSCALE_LOGIN_SERVER,
        })
    finally:
        db.close()


@api_app.post("/headscale/routes")
def headscale_routes():
    """
    Synchronise les routes Headscale approuvees pour le boitier authentifie
    sur exactement l'ensemble fourni (remplace toute approbation
    precedente). A appeler a chaque fois que le boitier recalcule ses routes
    locales (demarrage, changement de chantier -- voir
    services/network_config.py::publish_tailscale_routes()), pas seulement
    lors de l'enrolement initial.

    Headers:
        Authorization: Bearer <jeton_flotte>

    Payload:
        {
            "routes": ["10.42.0.0/24", "192.168.1.0/24"]
        }
        (liste vide ou absente = retire toutes les routes approuvees)

    Reponse:
        { "ok": true, "routes_approved": ["10.42.0.0/24", ...] }

    Sans effet (ok=true, routes_approved=[]) si le noeud Headscale
    correspondant n'existe pas encore (le boitier n'a pas encore fini son
    `tailscale up` apres l'enrolement).
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")
            hostname = boitier["hostname"]

            data = request.json or {}
            routes = data.get("routes") or []
            routes = [r.strip() for r in routes if isinstance(r, str) and r.strip()]

            approved = []
            try:
                node = _find_headscale_node(hostname)
                if node:
                    _ensure_fleet_tag(node)
                    _run_headscale(
                        [
                            "nodes", "approve-routes",
                            "--identifier", str(node["id"]),
                            "--routes", ",".join(routes),
                        ],
                        want_json=False,
                    )
                    approved = routes
            except Exception as exc:
                return json_error(500, f"Erreur approbation des routes : {exc}")

            cur.execute(
                "UPDATE boitier_registre SET last_sync_at = NOW() WHERE id = %s",
                (boitier["id"],),
            )
            log_write(cur, boitier["id"], "boitier_registre", hostname, "hs-routes")

        return json_ok({"routes_approved": approved})
    finally:
        db.close()
