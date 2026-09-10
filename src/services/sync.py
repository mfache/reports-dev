"""Route /sync : coeur de la synchronisation boitier <-> serveur central
(profils reseau, templates Modbus/BACnet, annotations, colonnes de table,
catalogue de points BACnet). Extrait d'api.py lors de la refonte (voir
CAHIER-DES-CHARGES-REFONTE.md).
"""
from __future__ import annotations

import gzip
import json

from bottle import request

from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok
from services.fleet import authenticate_boitier, log_write, notify_fleet_change
from services.chantiers import _resolve_or_create_chantier

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

