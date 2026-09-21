"""Routes for chantier pages and their JSON endpoints."""
from __future__ import annotations

import json
import urllib.parse

from bottle import request, response

from core.config import BASE_PATH
from core.database import get_db
from web.templating import get_current_user, render, view
from web.ui import error404_ui, ui_app
from web.ui_point_labels import _calc_trend, _load_template_point_labels, _resolve_point_label

@ui_app.get("/")
def reports_root():
    current_user = get_current_user()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('''
                SELECT c.id, c.ref, c.adresse, u.nom as charge_affaires,
                       GREATEST(c.date_modification, COALESCE(MAX(b.last_sync_at), '2000-01-01')) as date_modification,
                       SUM(CASE WHEN b.last_sync_at > DATE_SUB(NOW(), INTERVAL 15 MINUTE) THEN 1 ELSE 0 END) as active_boitiers
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                LEFT JOIN boitier_registre b ON b.chantier_id = c.id
                WHERE c.archive = 0
                GROUP BY c.id
                ORDER BY date_modification DESC
                LIMIT 5
            ''')
            recent_chantiers = cur.fetchall()

            cur.execute('''
                SELECT c.id, c.ref, c.adresse,
                   GREATEST(c.date_modification, COALESCE(MAX(b.last_sync_at), '2000-01-01')) as date_modification
                FROM chantiers c
                LEFT JOIN boitier_registre b ON b.chantier_id = c.id
                WHERE c.archive = 0 AND c.utilisateurs_id = %s
                GROUP BY c.id
                ORDER BY c.ref
            ''', (current_user['id'],))
            my_chantiers = cur.fetchall()

            cur.execute('''
                SELECT c.id, c.ref, c.adresse, u.nom as charge_affaires,
                       GREATEST(c.date_modification, COALESCE(MAX(b.last_sync_at), '2000-01-01')) as date_modification
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                LEFT JOIN boitier_registre b ON b.chantier_id = c.id
                WHERE c.archive = 0 AND (c.utilisateurs_id IS NULL OR c.utilisateurs_id != %s)
                GROUP BY c.id
                ORDER BY c.ref
            ''', (current_user['id'],))
            other_chantiers = cur.fetchall()

    finally:
        db.close()

    return view('home',
                title='Chantiers - Deltathermic',
                current_user=current_user,
                recent_chantiers=recent_chantiers,
                my_chantiers=my_chantiers,
                other_chantiers=other_chantiers)


@ui_app.post("/chantier/<chantier_id:int>/counts")
def chantier_counts(chantier_id):
    client_state = request.json or {}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT ref FROM chantiers WHERE id = %s", (chantier_id,))
            c_row = cur.fetchone()
            c_ref = c_row['ref'] if c_row else ""

            cur.execute('''
                SELECT t1.boitier_id, t1.protocol, t1.device, t1.obj, t2.c, t1.value
                FROM boitier_trends t1
                INNER JOIN (
                    SELECT t.boitier_id, t.protocol, t.device, t.obj, COUNT(*) as c, MAX(t.timestamp) as max_ts
                    FROM boitier_trends t
                    JOIN boitier_registre b ON t.boitier_id = b.hostname
                    WHERE b.chantier_id = %s AND t.site IN (%s, %s)
                    GROUP BY t.boitier_id, t.protocol, t.device, t.obj
                ) t2 ON t1.boitier_id = t2.boitier_id
                    AND t1.protocol = t2.protocol
                    AND t1.device = t2.device
                    AND t1.obj = t2.obj
                    AND t1.timestamp = t2.max_ts
                WHERE t1.site IN (%s, %s)
            ''', (chantier_id, str(chantier_id), c_ref, str(chantier_id), c_ref))
            counts = cur.fetchall()
    finally:
        db.close()

    diff = {}
    for row in counts:
        key = f"{row['boitier_id']}|{row['protocol']}|{row['device']}|{row['obj']}"
        server_val = row['c']
        client_val = client_state.get(key)

        if client_val != server_val:
            diff[key] = {'c': server_val, 'v': row['value']}

    return diff

@ui_app.post("/chantier/<chantier_id:int>/live-view")
def chantier_live_view(chantier_id):
    """
    Déclenche ou arrête le mode Live View pour un boitier.
    Publie un message MQTT que le RPI lira pour faire du fast-polling.
    """
    data = request.json or {}
    boitier_id = data.get('boitier_id')
    active = data.get('active', False)
    points = data.get('points', [])

    if not boitier_id:
        return {"error": "boitier_id manquant"}

    # On utilise le broker mqtt local
    import paho.mqtt.publish as mqtt_publish
    import json

    topic = f"dt/cmd/{boitier_id}/live_view"

    payload = {
        "action": "start" if active else "stop",
        "interval": 1, # intervalle en secondes
        "points": points
    }

    try:
        mqtt_publish.single(topic, json.dumps(payload), hostname="127.0.0.1")
        return {"status": "ok", "message": f"Ordre MQTT envoyé sur {topic}"}
    except Exception as e:
        return {"error": f"Erreur MQTT: {str(e)}"}

@ui_app.post("/chantier/<chantier_id:int>/chart-data")
def chantier_chart_data(chantier_id):
    points = request.json or []
    if not points:
        return {"datasets": []}

    db = get_db()
    datasets = []
    try:
        with db.cursor() as cur:
            cur.execute("SELECT ref FROM chantiers WHERE id = %s", (chantier_id,))
            c_row = cur.fetchone()
            c_ref = c_row['ref'] if c_row else ""

            tpl_labels = _load_template_point_labels(cur, list({pt['b'] for pt in points}), chantier_id)

            for pt in points:
                # Fetch label if available
                cur.execute('''
                    SELECT label FROM boitier_points_config
                    WHERE boitier_id=%s AND protocol=%s AND device=%s AND obj=%s
                    ORDER BY updated_at DESC LIMIT 1
                ''', (pt['b'], pt['p'], pt['d'], pt['o']))
                lbl_row = cur.fetchone()
                tpl_label = _resolve_point_label(tpl_labels, pt['b'], pt['p'], pt['d'], pt['o'])
                label = (lbl_row['label'] if lbl_row and lbl_row['label'] else None) or tpl_label or f"{pt['d']} / {pt['o']}"

                # Fetch aliases for bacnet
                if str(pt['p']).lower() == 'bacnet':
                    cur.execute('''
                        SELECT alias as value FROM chantier_bacnet_aliases
                        WHERE chantier_id=%s AND device_instance=%s
                    ''', (chantier_id, pt['d']))
                    alias_row = cur.fetchone()
                    if alias_row and alias_row['value']:
                        label = f"[{alias_row['value']}] {label}"

                # We limit to last 500 points to avoid overloading the browser for now
                cur.execute('''
                    SELECT timestamp, value
                    FROM boitier_trends
                    WHERE boitier_id=%s AND protocol=%s AND device=%s AND obj=%s AND site IN (%s, %s)
                    ORDER BY timestamp DESC
                    LIMIT 500
                ''', (pt['b'], pt['p'], pt['d'], pt['o'], str(chantier_id), c_ref))

                # cur.fetchall() renvoie parfois un tuple vide () quand il n'y a
                # aucun relevé pour ce point (au lieu d'une liste) : list() garantit
                # une methode .reverse() disponible dans tous les cas.
                rows = list(cur.fetchall())
                # Inverse pour obtenir l'ordre chronologique
                rows.reverse()

                data = []
                for r in rows:
                    try:
                        v = float(r['value'])
                        # x is timestamp in milliseconds
                        data.append({'x': int(r['timestamp']) * 1000, 'y': v})
                    except (ValueError, TypeError):
                        pass # Ignore non-numeric values for charting

                datasets.append({
                    "label": label,
                    "data": data,
                    "pointId": f"{pt['b']}|{pt['p']}|{pt['d']}|{pt['o']}"
                })
    finally:
        db.close()

    return {"datasets": datasets}


@ui_app.get("/chantier/<chantier_id:int>")
def chantier_details(chantier_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('''
                SELECT c.*, u.nom as charge_affaires
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                WHERE c.id = %s
            ''', (chantier_id,))
            chantier = cur.fetchone()

            if not chantier:
                return error404_ui(None)
    finally:
        db.close()

    chart_param = request.query.get("chart")
    manifest_url = f"{BASE_PATH}/manifest.json"
    if chart_param:
        encoded_start = urllib.parse.quote(f"{BASE_PATH}/chantier/{chantier_id}?chart={chart_param}")
        manifest_url = f"{BASE_PATH}/manifest.json?start={encoded_start}"

    return view('chantier',
                title=f"Chantier {chantier['ref']} - Deltathermic",
                chantier=chantier,
                manifest_url=manifest_url)


@ui_app.get("/chantier/<chantier_id:int>/boitiers")
def chantier_boitiers(chantier_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, ref FROM chantiers WHERE id = %s", (chantier_id,))
            chantier = cur.fetchone()

            if not chantier:
                return error404_ui(None)

            # Get boitiers for this chantier
            cur.execute('''
                SELECT hostname, tailscale_name
                FROM boitier_registre
                WHERE chantier_id = %s
                ORDER BY hostname
            ''', (chantier_id,))
            boitiers_rows = cur.fetchall()

            boitiers = {row['hostname']: {'tailscale_name': row['tailscale_name'], 'points': []} for row in boitiers_rows}

            bacnet_aliases = {}
            if boitiers_rows:
                hostnames = [row['hostname'] for row in boitiers_rows]
                format_strings = ','.join(['%s'] * len(hostnames))

                # Fetch points config
                cur.execute(f'''
                    SELECT boitier_id, protocol, device, obj, MAX(label) as label
                    FROM (
                        SELECT boitier_id, protocol, device, obj, label
                        FROM boitier_points_config
                        WHERE boitier_id IN ({format_strings}) AND site IN (%s, %s)
                        UNION
                        SELECT boitier_id, protocol, device, obj, NULL as label
                        FROM boitier_trends
                        WHERE boitier_id IN ({format_strings}) AND site IN (%s, %s)
                    ) as combined
                    GROUP BY boitier_id, protocol, device, obj
                    ORDER BY boitier_id, protocol, device, obj
                ''', tuple(hostnames) + (str(chantier['id']), chantier['ref']) + tuple(hostnames) + (str(chantier['id']), chantier['ref']))
                points = cur.fetchall()

                # Fetch trend stats using window function ROW_NUMBER
                cur.execute(f'''
                    WITH ranked AS (
                        SELECT boitier_id, protocol, device, obj, value, timestamp,
                               ROW_NUMBER() OVER (PARTITION BY boitier_id, protocol, device, obj ORDER BY timestamp DESC) as rn,
                               COUNT(*) OVER (PARTITION BY boitier_id, protocol, device, obj) as trend_count
                        FROM boitier_trends
                        WHERE boitier_id IN ({format_strings}) AND site IN (%s, %s)
                    )
                    SELECT
                        r1.boitier_id, r1.protocol, r1.device, r1.obj, r1.trend_count,
                        r1.value as current_val,
                        r2.value as previous_val
                    FROM ranked r1
                    LEFT JOIN ranked r2 ON r1.boitier_id = r2.boitier_id
                                       AND r1.protocol = r2.protocol
                                       AND r1.device = r2.device
                                       AND r1.obj = r2.obj
                                       AND r2.rn = 2
                    WHERE r1.rn = 1
                ''', tuple(hostnames) + (str(chantier['id']), chantier['ref']))

                trend_data = {(r['boitier_id'], r['protocol'], str(r['device']), str(r['obj'])): r for r in cur.fetchall()}

                # Libelle via le template partage (source de vérité), utilisé
                # seulement si boitier_points_config n'a rien fourni pour ce
                # point : voir _load_template_point_labels ci-dessus.
                tpl_labels = _load_template_point_labels(cur, hostnames, chantier['id'])

                for p in points:
                    if not p['label']:
                        p['label'] = _resolve_point_label(tpl_labels, p['boitier_id'], p['protocol'], p['device'], p['obj'])

                    key = (p['boitier_id'], p['protocol'], str(p['device']), str(p['obj']))
                    t_data = trend_data.get(key)
                    if t_data:
                        p['trend_count'] = t_data['trend_count']
                        p['last_value'] = t_data['current_val']
                        p['trend_dir'] = _calc_trend(t_data['current_val'], t_data['previous_val'])
                    else:
                        p['trend_count'] = 0
                        p['last_value'] = None
                        p['trend_dir'] = ""
                    if p['boitier_id'] in boitiers:
                        boitiers[p['boitier_id']]['points'].append(p)

                # Get aliases for bacnet devices
                cur.execute('''
                    SELECT device_instance as entry_key, alias as value
                    FROM chantier_bacnet_aliases
                    WHERE chantier_id = %s
                ''', (chantier_id,))
                bacnet_aliases = {row['entry_key']: row['value'] for row in cur.fetchall()}

    finally:
        db.close()

    return render('chantier_boitiers',
                  chantier=chantier,
                  boitiers=boitiers,
                  bacnet_aliases=bacnet_aliases)



@ui_app.post("/chantier/<chantier_id:int>/purge")
def chantier_purge(chantier_id):
    """Purger les relevés (trends) d'un chantier complet ou d'un équipement (device) spécifique."""
    data = request.json or {}
    device = request.forms.get("device") or data.get("device")
    boitier_id = request.forms.get("boitier_id") or data.get("boitier_id")
    protocol = request.forms.get("protocol") or data.get("protocol")

    db = get_db()
    deleted_count = 0
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, ref FROM chantiers WHERE id = %s", (chantier_id,))
            chantier = cur.fetchone()
            if not chantier:
                response.status = 404
                return {"error": "Chantier introuvable."}
            c_ref = chantier['ref']

            cur.execute("SELECT hostname FROM boitier_registre WHERE chantier_id = %s", (chantier_id,))
            boitier_rows = cur.fetchall()
            hostnames = [r['hostname'] for r in boitier_rows]

            site_values = (str(chantier_id), c_ref)

            if device:
                if boitier_id:
                    if protocol:
                        cur.execute('''
                            DELETE FROM boitier_trends
                            WHERE site IN (%s, %s) AND boitier_id = %s AND protocol = %s AND device = %s
                        ''', (site_values[0], site_values[1], boitier_id, protocol, device))
                    else:
                        cur.execute('''
                            DELETE FROM boitier_trends
                            WHERE site IN (%s, %s) AND boitier_id = %s AND device = %s
                        ''', (site_values[0], site_values[1], boitier_id, device))
                else:
                    cur.execute('''
                        DELETE FROM boitier_trends
                        WHERE site IN (%s, %s) AND device = %s
                    ''', (site_values[0], site_values[1], device))
            else:
                if hostnames:
                    format_strings = ','.join(['%s'] * len(hostnames))
                    cur.execute(f'''
                        DELETE FROM boitier_trends
                        WHERE site IN (%s, %s) OR (boitier_id IN ({format_strings}) AND site IN (%s, %s))
                    ''', (site_values[0], site_values[1]) + tuple(hostnames) + (site_values[0], site_values[1]))
                else:
                    cur.execute('''
                        DELETE FROM boitier_trends
                        WHERE site IN (%s, %s)
                    ''', (site_values[0], site_values[1]))

            deleted_count = cur.rowcount
    except Exception as e:
        response.status = 500
        return {"error": f"Erreur lors de la purge : {str(e)}"}
    finally:
        db.close()

    return {"status": "ok", "deleted": deleted_count, "message": f"{deleted_count} relevé(s) supprimé(s)."}



@ui_app.get("/chantier/<chantier_id:int>/graph")
def chantier_graph_view(chantier_id):
    """Page minimale, sans tableau ni navigation, destinee au scan de QR
    code depuis un smartphone : uniquement le graphique des points choisis.
    Reutilise le meme endpoint /chart-data que la modale de la page complete.
    """
    chart_param = request.query.get("chart", "")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, ref FROM chantiers WHERE id = %s", (chantier_id,))
            chantier = cur.fetchone()
    finally:
        db.close()

    if not chantier:
        return error404_ui(None)

    manifest_url = f"{BASE_PATH}/manifest.json"
    if chart_param:
        encoded_start = urllib.parse.quote(f"{BASE_PATH}/chantier/{chantier_id}/graph?chart={chart_param}")
        manifest_url = f"{BASE_PATH}/manifest.json?start={encoded_start}"

    return render('chart_view',
                chantier=chantier,
                chart_param_json=json.dumps(chart_param),
                manifest_url=manifest_url)
