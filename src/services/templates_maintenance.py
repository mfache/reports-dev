"""Maintenance des templates Modbus partages par la flotte : vue
d'ensemble par revision, comparaison (diff) entre deux revisions,
depreciation et suppression. Extrait d'ui.py lors de la refonte (voir
CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import json

from bottle import request, response, template

from core.database import get_db
from web.ui import ui_app, format_human_date

def compute_template_diff(def1, def2):
    """
    Compare deux définitions de templates Modbus et retourne les différences.
    """
    reads1 = def1.get("reads", []) if isinstance(def1, dict) else []
    reads2 = def2.get("reads", []) if isinstance(def2, dict) else []

    # Map by function:address
    map1 = {f"{r.get('function', 3)}:{r.get('address', r.get('reg', 0))}": r for r in reads1}
    map2 = {f"{r.get('function', 3)}:{r.get('address', r.get('reg', 0))}": r for r in reads2}

    all_keys = sorted(list(set(map1.keys()) | set(map2.keys())), key=lambda k: (int(k.split(':')[0]), int(k.split(':')[1])))

    diff_registers = []
    for k in all_keys:
        r1 = map1.get(k)
        r2 = map2.get(k)
        if r1 is None and r2 is not None:
            diff_registers.append({
                "status": "added",
                "key": k,
                "reg": r2.get("address", r2.get("reg", 0)),
                "function": r2.get("function", 3),
                "name": r2.get("label") or r2.get("name", ""),
                "type": r2.get("type", "u16"),
                "scale": r2.get("scale", 1.0),
                "unit": r2.get("unit", ""),
                "changes": {}
            })
        elif r1 is not None and r2 is None:
            diff_registers.append({
                "status": "removed",
                "key": k,
                "reg": r1.get("address", r1.get("reg", 0)),
                "function": r1.get("function", 3),
                "name": r1.get("label") or r1.get("name", ""),
                "type": r1.get("type", "u16"),
                "scale": r1.get("scale", 1.0),
                "unit": r1.get("unit", ""),
                "changes": {}
            })
        else:
            changes = {}
            for attr in ["name", "label", "type", "scale", "unit"]:
                v1 = r1.get(attr)
                v2 = r2.get(attr)
                if attr in ("name", "label"):
                    l1 = r1.get("label") or r1.get("name", "")
                    l2 = r2.get("label") or r2.get("name", "")
                    if l1 != l2:
                        changes["name"] = {"old": l1, "new": l2}
                elif v1 != v2 and (v1 is not None or v2 is not None):
                    changes[attr] = {"old": v1, "new": v2}

            if changes:
                diff_registers.append({
                    "status": "modified",
                    "key": k,
                    "reg": r2.get("address", r2.get("reg", 0)),
                    "function": r2.get("function", 3),
                    "name": r2.get("label") or r2.get("name", ""),
                    "type": r2.get("type", "u16"),
                    "scale": r2.get("scale", 1.0),
                    "unit": r2.get("unit", ""),
                    "changes": changes
                })
            else:
                diff_registers.append({
                    "status": "unchanged",
                    "key": k,
                    "reg": r2.get("address", r2.get("reg", 0)),
                    "function": r2.get("function", 3),
                    "name": r2.get("label") or r2.get("name", ""),
                    "type": r2.get("type", "u16"),
                    "scale": r2.get("scale", 1.0),
                    "unit": r2.get("unit", ""),
                    "changes": {}
                })

    meta_changes = {}
    if isinstance(def1, dict) and isinstance(def2, dict):
        for meta_key in ["base", "port", "unit", "notes"]:
            m1 = def1.get(meta_key)
            m2 = def2.get(meta_key)
            if m1 != m2 and (m1 is not None or m2 is not None):
                meta_changes[meta_key] = {"old": m1, "new": m2}

    return {
        "registers": diff_registers,
        "meta_changes": meta_changes,
        "added_count": len([r for r in diff_registers if r["status"] == "added"]),
        "removed_count": len([r for r in diff_registers if r["status"] == "removed"]),
        "modified_count": len([r for r in diff_registers if r["status"] == "modified"]),
        "unchanged_count": len([r for r in diff_registers if r["status"] == "unchanged"])
    }


@ui_app.get("/maintenance/templates")
def templates_maintenance_view():
    user_id = request.query.get("uid", "1")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = %s", (user_id,))
            current_user = cur.fetchone()
            if not current_user:
                current_user = {"id": 1, "nom": "Admin", "cas": 0, "adm": 1}

            cur.execute("SELECT id, nom, cas FROM utilisateurs ORDER BY nom")
            all_users = cur.fetchall()

            cur.execute("""
                SELECT t.id, t.template_uuid, t.revision_uuid, t.parent_revision_uuid,
                       t.name, t.manufacturer, t.version, t.definition_json,
                       t.created_by_node, t.is_deprecated, t.date_creation, t.date_modification,
                       COUNT(DISTINCT u.boitier_id) as active_boitiers_count,
                       COUNT(u.device_name) as active_devices_count,
                       GROUP_CONCAT(DISTINCT u.boitier_id ORDER BY u.boitier_id SEPARATOR ', ') as using_boitiers,
                       GROUP_CONCAT(DISTINCT CONCAT(u.boitier_id, ' (', u.device_name, ')') ORDER BY u.boitier_id SEPARATOR ', ') as device_details
                FROM boitier_modbus_templates t
                LEFT JOIN boitier_template_usage u ON t.revision_uuid = u.revision_uuid
                GROUP BY t.id
                ORDER BY t.name ASC, t.version DESC
            """)
            rows = cur.fetchall()

            templates_by_uuid = {}
            for r in rows:
                t_uuid = r["template_uuid"]
                if t_uuid not in templates_by_uuid:
                    templates_by_uuid[t_uuid] = {
                        "template_uuid": t_uuid,
                        "name": r["name"],
                        "manufacturer": r["manufacturer"] or "",
                        "revisions": [],
                        "total_active_boitiers": 0,
                        "total_active_devices": 0
                    }
                try:
                    def_data = json.loads(r["definition_json"])
                    reads_count = len(def_data.get("reads", []))
                except Exception:
                    def_data = {}
                    reads_count = 0

                rev_info = dict(r)
                rev_info["reads_count"] = reads_count
                rev_info["definition"] = def_data
                templates_by_uuid[t_uuid]["revisions"].append(rev_info)
                templates_by_uuid[t_uuid]["total_active_boitiers"] += r["active_boitiers_count"]
                templates_by_uuid[t_uuid]["total_active_devices"] += r["active_devices_count"]

    finally:
        db.close()

    templates_data_json = json.dumps(templates_by_uuid, default=str)
    return template('templates_maintenance',
                    templates_data_json=templates_data_json,
                    current_user=current_user,
                    all_users=all_users,
                    templates_by_uuid=templates_by_uuid,
                    format_human_date=format_human_date)


@ui_app.get("/maintenance/templates/diff-data")
def templates_diff_data():
    rev1_uuid = request.query.get("rev1", "").strip()
    rev2_uuid = request.query.get("rev2", "").strip()
    if not rev1_uuid or not rev2_uuid:
        response.status = 400
        return {"ok": False, "error": "Les deux révisions sont requises (rev1, rev2)."}

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, name, version, created_by_node, definition_json FROM boitier_modbus_templates WHERE revision_uuid=%s", (rev1_uuid,))
            r1 = cur.fetchone()
            cur.execute("SELECT id, name, version, created_by_node, definition_json FROM boitier_modbus_templates WHERE revision_uuid=%s", (rev2_uuid,))
            r2 = cur.fetchone()
    finally:
        db.close()

    if not r1 or not r2:
        response.status = 404
        return {"ok": False, "error": "Une ou les deux révisions sont introuvables."}

    try:
        def1 = json.loads(r1["definition_json"])
    except Exception:
        def1 = {}
    try:
        def2 = json.loads(r2["definition_json"])
    except Exception:
        def2 = {}

    diff = compute_template_diff(def1, def2)
    return {
        "ok": True,
        "diff": diff,
        "rev1": {
            "name": r1["name"],
            "version": r1["version"],
            "created_by_node": r1["created_by_node"],
            "reads_count": len(def1.get("reads", []))
        },
        "rev2": {
            "name": r2["name"],
            "version": r2["version"],
            "created_by_node": r2["created_by_node"],
            "reads_count": len(def2.get("reads", []))
        }
    }


@ui_app.post("/maintenance/templates/toggle_deprecate")
def templates_toggle_deprecate():
    data = request.json or {}
    rev_uuid = (data.get("revision_uuid") or "").strip()
    if not rev_uuid:
        response.status = 400
        return {"ok": False, "error": "revision_uuid requis."}

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE boitier_modbus_templates SET is_deprecated = 1 - is_deprecated WHERE revision_uuid = %s", (rev_uuid,))
            if cur.rowcount == 0:
                response.status = 404
                return {"ok": False, "error": "Révision introuvable."}
    finally:
        db.close()

    return {"ok": True, "message": "Statut mis à jour."}


@ui_app.post("/maintenance/templates/delete")
def templates_delete():
    data = request.json or {}
    rev_uuid = (data.get("revision_uuid") or "").strip()
    if not rev_uuid:
        response.status = 400
        return {"ok": False, "error": "revision_uuid requis."}

    db = get_db()
    try:
        with db.cursor() as cur:
            # Règle de sécurité stricte : vérification qu'aucun boîtier n'utilise cette version
            cur.execute("""
                SELECT COUNT(DISTINCT boitier_id) as cnt,
                       GROUP_CONCAT(DISTINCT boitier_id SEPARATOR ', ') as boitiers
                FROM boitier_template_usage
                WHERE revision_uuid = %s
            """, (rev_uuid,))
            usage_row = cur.fetchone()
            active_count = usage_row["cnt"] if usage_row else 0
            if active_count > 0:
                response.status = 400
                return {
                    "ok": False,
                    "error": f"Suppression refusée : cette version est activement utilisée par {active_count} boîtier(s) ({usage_row['boitiers']})."
                }

            cur.execute("DELETE FROM boitier_modbus_templates WHERE revision_uuid = %s", (rev_uuid,))
            if cur.rowcount == 0:
                response.status = 404
                return {"ok": False, "error": "Révision introuvable."}
    finally:
        db.close()

    return {"ok": True, "message": "Révision supprimée avec succès."}
