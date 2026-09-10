"""Point d'entree de l'UI web `reports` : cree `ui_app`, les pages
principales (accueil, chantier, noeuds, console SQL, page /dev), puis
importe `web.stream` et `services.templates_maintenance` pour que leurs
routes s'enregistrent sur `ui_app` (effet de bord de l'import).

Sur le modele rpinode/src/web : extrait d'ui.py lors de la refonte (voir
CAHIER-DES-CHARGES-REFONTE.md). Contrairement a web/api.py, la majorite
des routes reste ici (SSE et maintenance des templates sont les deux
seuls sous-domaines suffisamment autonomes pour justifier un fichier a
part) - meme nuance assumee qu'au decoupage d'api.py : chaque route
garde sa logique et ses requetes SQL inline.

Ordre d'import important : `ui_app` doit exister avant que
`web.stream` et `services.templates_maintenance` ne fassent
`from web.ui import ui_app` pour y enregistrer leurs routes.
"""
from __future__ import annotations

import json
import urllib.parse
import datetime

from bottle import Bottle, request, response, static_file, template, TEMPLATE_PATH

from core.database import get_db
from core.config import BASE_PATH
from core.paths import TEMPLATES_DIR, STATIC_DIR

def format_human_date(dt):
    if not dt:
        return "-"
    now = datetime.datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "Il y a moins d'une minute"
    elif seconds < 1800:
        return "Il y a quelques minutes"
    elif seconds < 7200:
        return "Il y a une demi-heure"

    today = now.date()
    dt_date = dt.date()
    days_diff = (today - dt_date).days

    if days_diff == 0:
        return "Aujourd'hui"
    elif days_diff == 1:
        return "Hier"
    elif days_diff < 7:
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return jours[dt.weekday()]
    elif days_diff < 14:
        return "La semaine passée"
    elif days_diff < 21:
        return "Il y a deux semaines"
    else:
        return dt.strftime("%d/%m/%Y")

def _calc_trend(curr, prev):
    if curr is None or prev is None:
        return ""
    if curr == prev:
        return "stable"
    try:
        cf = float(curr)
        pf = float(prev)
        if cf > pf: return "up"
        if cf < pf: return "down"
        return "stable"
    except ValueError:
        return "diff"

ui_app = Bottle()
TEMPLATE_PATH.append(str(TEMPLATES_DIR))

@ui_app.error(404)
def error404_ui(error):
    return template('404')


@ui_app.get("/static/<filepath:path>")
def serve_static(filepath):
    return static_file(filepath, root=str(STATIC_DIR))


@ui_app.get("/sw.js")
def serve_sw():
    res = static_file("sw.js", root=str(STATIC_DIR), mimetype="application/javascript")
    res.set_header("Service-Worker-Allowed", f"{BASE_PATH}/")
    return res


@ui_app.get("/manifest.json")
def serve_manifest():
    start = request.query.get("start")
    if start:
        import json
        try:
            with open(STATIC_DIR / "manifest.json", "r") as f:
                data = json.load(f)
            data["start_url"] = start
            data["name"] = "Graphique Delta Thermic"
            data["short_name"] = "DT Graph"
            response.content_type = "application/manifest+json"
            return json.dumps(data)
        except Exception:
            pass
    return static_file("manifest.json", root=str(STATIC_DIR), mimetype="application/manifest+json")


@ui_app.get("/")
def reports_root():
    user_id = request.query.get("uid", "1")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = %s", (user_id,))
            current_user = cur.fetchone()
            if not current_user:
                return "Utilisateur introuvable."

            cur.execute("SELECT id, nom, cas FROM utilisateurs ORDER BY nom")
            all_users = cur.fetchall()

            cur.execute('''
                SELECT c.id, c.ref, c.adresse, u.nom as charge_affaires, 
                       GREATEST(c.date_modification, COALESCE(MAX(b.last_sync_at), '2000-01-01')) as date_modification
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                LEFT JOIN boitier_registre b ON b.chantier_id = c.id
                WHERE c.archive = 0
                GROUP BY c.id
                ORDER BY date_modification DESC
                LIMIT 5
            ''')
            recent_chantiers = cur.fetchall()

            my_chantiers = []
            if current_user['cas'] == 1:
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
                WHERE c.archive = 0 AND c.utilisateurs_id != %s
                GROUP BY c.id
                ORDER BY c.ref
            ''', (current_user['id'],))
            other_chantiers = cur.fetchall()

    finally:
        db.close()

    return template('home',
                    current_user=current_user,
                    all_users=all_users,
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
            for pt in points:
                # Fetch label if available
                cur.execute('''
                    SELECT label FROM boitier_points_config
                    WHERE boitier_id=%s AND protocol=%s AND device=%s AND obj=%s
                    ORDER BY updated_at DESC LIMIT 1
                ''', (pt['b'], pt['p'], pt['d'], pt['o']))
                lbl_row = cur.fetchone()
                label = lbl_row['label'] if lbl_row and lbl_row['label'] else f"{pt['d']} / {pt['o']}"

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
    user_id = request.query.get("uid", "1")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = %s", (user_id,))
            current_user = cur.fetchone()
            if not current_user:
                return "Utilisateur introuvable."

            cur.execute("SELECT id, nom, cas FROM utilisateurs ORDER BY nom")
            all_users = cur.fetchall()

            cur.execute('''
                SELECT c.*, u.nom as charge_affaires
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                WHERE c.id = %s
            ''', (chantier_id,))
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

                # Fetch trends count, last value, and previous value
                cur.execute(f'''
                    SELECT t1.boitier_id, t1.protocol, t1.device, t1.obj, t2.c as trend_count, t1.value as current_val,
                           (SELECT value FROM boitier_trends t_sub
                            WHERE t_sub.boitier_id = t1.boitier_id
                              AND t_sub.protocol = t1.protocol
                              AND t_sub.device = t1.device
                              AND t_sub.obj = t1.obj
                              AND t_sub.site IN (%s, %s)
                              AND t_sub.timestamp < t2.max_ts
                            ORDER BY t_sub.timestamp DESC LIMIT 1) as previous_val
                    FROM boitier_trends t1
                    INNER JOIN (
                        SELECT boitier_id, protocol, device, obj, COUNT(*) as c, MAX(timestamp) as max_ts
                        FROM boitier_trends
                        WHERE boitier_id IN ({format_strings}) AND site IN (%s, %s)
                        GROUP BY boitier_id, protocol, device, obj
                    ) t2 ON t1.boitier_id = t2.boitier_id
                        AND t1.protocol = t2.protocol
                        AND t1.device = t2.device
                        AND t1.obj = t2.obj
                        AND t1.timestamp = t2.max_ts
                    WHERE t1.site IN (%s, %s)
                ''', (str(chantier['id']), chantier['ref']) + tuple(hostnames) + (str(chantier['id']), chantier['ref']) + (str(chantier['id']), chantier['ref']))

                trend_data = {(r['boitier_id'], r['protocol'], str(r['device']), str(r['obj'])): r for r in cur.fetchall()}

                for p in points:
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

    chart_param = request.query.get("chart")
    manifest_url = f"{BASE_PATH}/manifest.json"
    if chart_param:
        encoded_start = urllib.parse.quote(f"{BASE_PATH}/chantier/{chantier_id}?chart={chart_param}")
        manifest_url = f"{BASE_PATH}/manifest.json?start={encoded_start}"

    return template('chantier',
                    current_user=current_user,
                    all_users=all_users,
                    chantier=chantier,
                    boitiers=boitiers,
                    bacnet_aliases=bacnet_aliases,
                    manifest_url=manifest_url)



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

    return template('chart_view',
                    chantier=chantier,
                    chart_param_json=json.dumps(chart_param),
                    manifest_url=manifest_url)



@ui_app.get("/nodes")
def nodes_view():
    user_id = request.query.get("uid", "1")
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = %s", (user_id,))
            current_user = cur.fetchone()

            cur.execute("SELECT id, nom, cas FROM utilisateurs ORDER BY nom")
            all_users = cur.fetchall()

            cur.execute('''
                SELECT b.id, b.hostname, b.tailscale_name, b.last_sync_at, b.last_ip, c.ref as chantier_ref
                FROM boitier_registre b
                LEFT JOIN chantiers c ON b.chantier_id = c.id
                ORDER BY b.id
            ''')
            boitiers = cur.fetchall()

            cur.execute('SELECT boitier_id, COUNT(*) as c FROM boitier_trends GROUP BY boitier_id')
            trends_count = {row['boitier_id']: row['c'] for row in cur.fetchall()}

            cur.execute('SELECT boitier_id, COUNT(*) as c FROM boitier_points_config GROUP BY boitier_id')
            config_count = {row['boitier_id']: row['c'] for row in cur.fetchall()}
    finally:
        db.close()

    return template('nodes',
                    current_user=current_user,
                    all_users=all_users,
                    boitiers=boitiers,
                    trends_count=trends_count,
                    config_count=config_count,
                    format_human_date=format_human_date)


@ui_app.post("/sql")
def execute_sql():
    db = get_db()
    query = (request.json or {}).get("query", "").strip()
    if not query:
        return json.dumps({"error": "Requête vide."})

    try:
        with db.cursor() as cur:
            cur.execute(query)
            is_select = query.upper().startswith(("SELECT", "SHOW", "DESCRIBE", "EXPLAIN"))
            if is_select:
                rows = cur.fetchall()
                columns = list(rows[0].keys()) if rows else []
                return json.dumps({"columns": columns, "rows": rows}, default=str)
            else:
                return json.dumps({"message": f"Requête exécutée avec succès. {cur.rowcount} ligne(s) affectée(s)."})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


@ui_app.get("/dev")
def dev():
    tab = request.query.get("tab", "sql")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Espace Développeur - Delta Thermic</title>
    <link rel="manifest" href="{BASE_PATH}/manifest.json">
    <meta name="theme-color" content="#0056b3">
    <link rel="apple-touch-icon" href="{BASE_PATH}/static/dticon.png">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }}
        h1, h2 {{ color: #0056b3; }}
        .mermaid {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow-x: auto; margin-bottom: 30px; display: flex; justify-content: center; }}
        table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 40px; font-size: 0.9em; }}
        th, td {{ border: 1px solid #e1e1e1; padding: 10px; text-align: left; }}
        th {{ background-color: #f2f2f2; font-weight: bold; color: #444; }}
        tr:nth-child(even) {{ background-color: #fcfcfc; }}
        code {{ background: #eee; padding: 2px 5px; border-radius: 4px; color: #d63384; font-weight: bold; }}

        .sql-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 30px; border-left: 4px solid #0056b3; }}
        textarea {{ width: 100%; height: 100px; padding: 10px; font-family: monospace; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 10px; box-sizing: border-box; }}
        button {{ background: #0056b3; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }}
        button:hover {{ background: #004494; }}
        .error-msg {{ color: #c62828; font-weight: bold; margin-top: 10px; background: #ffebee; padding: 10px; border-radius: 4px; display: inline-block; }}
        .success-msg {{ color: #2e7d32; font-weight: bold; margin-top: 10px; background: #e8f5e9; padding: 10px; border-radius: 4px; display: inline-block; }}
        
        .nav-tabs {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 30px; display: flex; gap: 20px; border-left: 4px solid #0056b3; }}
        .nav-tabs a {{ text-decoration: none; font-weight: bold; padding-bottom: 5px; transition: color 0.2s; }}
        .tab-active {{ color: #0056b3; border-bottom: 2px solid #0056b3; }}
        .tab-inactive {{ color: #666; border-bottom: 2px solid transparent; }}
        .tab-inactive:hover {{ color: #0056b3; }}
    </style>
    <!-- Chargement de Mermaid JS pour rendre le diagramme -->
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</head>
<body>
    <h1>🛠️ Espace Développeur</h1>
    
    <div class="nav-tabs">
        <a href="?tab=sql" class="{'tab-active' if tab == 'sql' else 'tab-inactive'}">Base de données & SQL</a>
        <a href="?tab=api" class="{'tab-active' if tab == 'api' else 'tab-inactive'}">Documentation API</a>
    </div>
"""

    if tab == "sql":
        db = get_db()
        tables_info = {}
        foreign_keys = []
        tables = []
        
        try:
            with db.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = [list(r.values())[0] for r in cur.fetchall()]

                # Récupération des clés étrangères
                cur.execute("""
                    SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE REFERENCED_TABLE_SCHEMA = 'dt' AND REFERENCED_TABLE_NAME IS NOT NULL
                """)
                foreign_keys = cur.fetchall()

                # Détails de chaque table
                for table in tables:
                    cur.execute(f"DESCRIBE {table}")
                    tables_info[table] = cur.fetchall()
        finally:
            db.close()

        # Génération du code Mermaid pour le diagramme Entité-Association
        mermaid_code = "erDiagram\n"
        for fk in foreign_keys:
            mermaid_code += f"    {fk['REFERENCED_TABLE_NAME']} ||--o{{ {fk['TABLE_NAME']} : \"{fk['COLUMN_NAME']}\"\n"

        for table, cols in tables_info.items():
            mermaid_code += f"    {table} {{\n"
            for col in cols:
                pk = " PK" if col['Key'] == 'PRI' else (" FK" if col['Key'] == 'MUL' else "")
                ctype = col['Type'].split('(')[0].replace(' ', '_').replace(',', '_')
                mermaid_code += f"        {ctype} {col['Field']}{pk}\n"
            mermaid_code += "    }\n"
            
        html += f"""
    <h2>🗄️ Structure de la base MariaDB</h2>

    <div class="sql-container">
        <h2 style="margin-top: 0;">Console SQL</h2>
        <textarea id="sql-query" placeholder="SELECT * FROM chantiers LIMIT 5;"></textarea>
        <button onclick="executeSQL()">Exécuter la requête</button>
        <div id="sql-result" style="margin-top: 15px; overflow-x: auto;"></div>
    </div>

    <script>
    async function executeSQL() {{
        const query = document.getElementById('sql-query').value.trim();
        const resultDiv = document.getElementById('sql-result');
        if (!query) return;

        resultDiv.innerHTML = '<span style="color: #666;">Exécution en cours...</span>';

        try {{
            const res = await fetch('{BASE_PATH}/sql', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ query: query }})
            }});

            const data = await res.json();

            if (data.error) {{
                resultDiv.innerHTML = `<div class="error-msg">❌ Erreur : ${{data.error}}</div>`;
            }} else if (data.message) {{
                resultDiv.innerHTML = `<div class="success-msg">✅ ${{data.message}}</div>`;
            }} else if (data.columns && data.rows) {{
                if (data.rows.length === 0) {{
                    resultDiv.innerHTML = '<span style="color: #666;">Requête exécutée : 0 résultat.</span>';
                }} else {{
                    let tableHtml = '<table><thead><tr>';
                    data.columns.forEach(col => {{
                        tableHtml += `<th>${{col}}</th>`;
                    }});
                    tableHtml += '</tr></thead><tbody>';

                    data.rows.forEach(row => {{
                        tableHtml += '<tr>';
                        data.columns.forEach(col => {{
                            let val = row[col];
                            if (val === null) val = '<span style="color: #aaa; font-style: italic;">NULL</span>';
                            tableHtml += `<td>${{val}}</td>`;
                        }});
                        tableHtml += '</tr>';
                    }});

                    tableHtml += '</tbody></table>';
                    resultDiv.innerHTML = `<div class="success-msg" style="margin-bottom: 10px;">✅ ${{data.rows.length}} ligne(s) récupérée(s).</div>` + tableHtml;
                }}
            }}
        }} catch (e) {{
            resultDiv.innerHTML = `<div class="error-msg">❌ Erreur réseau ou de parsing : ${{e.message}}</div>`;
        }}
    }}
    </script>

    <p>Aperçu généré dynamiquement du schéma de base de données.</p>

    <h2>Diagramme Entité-Association (ER)</h2>
    <div class="mermaid">
{mermaid_code}
    </div>

    <h2>Détail des tables ({len(tables)})</h2>
"""
        for table, cols in tables_info.items():
            html += f"<h3>Table : <code>{table}</code></h3><table><tr><th>Champ</th><th>Type</th><th>Null</th><th>Clé</th><th>Défaut</th><th>Extra</th></tr>"
            for col in cols:
                html += f"<tr><td>{col['Field']}</td><td style='font-family: monospace;'>{col['Type']}</td><td>{col['Null']}</td><td><strong>{col['Key']}</strong></td><td>{col['Default']}</td><td><span style='color: #888; font-size: 0.9em;'>{col['Extra']}</span></td></tr>"
            html += "</table>"
            
    elif tab == "api":
        from web.api import api_app

        # Extraction dynamique de la documentation des API a partir du
        # registre de routes Bottle (api_app.routes). Avant la refonte du
        # 10 septembre 2026, ce bloc faisait `import api` puis relisait le
        # code source de ce fichier monolithique pour retrouver, ligne par
        # ligne, le decorateur @api_app.get/post au-dessus de chaque
        # fonction. Casse par l'eclatement d'api.py en web/api.py +
        # services/*.py (plus de module `api` unique a inspecter).
        # api_app.routes expose directement route.rule et route.method,
        # plus robuste et plus simple que le parsing de source.
        api_docs = []
        for route in api_app.routes:
            obj = route.callback
            if not (obj and hasattr(obj, '__doc__') and obj.__doc__):
                continue
            doc = obj.__doc__.strip()
            # On ne prend que les fonctions qui ont été décorées comme routes (on cherche une description dans la docstring)
            if "Réponse:" in doc:
                # Extraction basique des différentes parties
                desc = doc.split("Usage:")[0].split("Headers:")[0].split("Payload:")[0].strip()
                usage = ""
                if "Usage:" in doc:
                    usage = doc.split("Usage:")[1].split("Réponse:")[0].strip()
                payload = ""
                if "Payload:" in doc:
                    payload = doc.split("Payload:")[1].split("Réponse:")[0].strip()
                    if "Headers:" in payload:
                        payload = payload.split("Headers:")[0].strip()
                headers = ""
                if "Headers:" in doc:
                    headers = doc.split("Headers:")[1].split("Payload:")[0].split("Usage:")[0].split("Réponse:")[0].strip()
                reponse = doc.split("Réponse:")[1].strip()

                api_docs.append({
                    "method": route.method,
                    "endpoint": route.rule,
                    "desc": desc,
                    "headers": headers,
                    "payload": payload,
                    "usage": usage,
                    "reponse": reponse
                })
        
        html += f"""
    <h2>📖 Documentation des API Boîtiers</h2>
    <p>Liste des endpoints disponibles (préfixe <code>{BASE_PATH}/api</code>) pour la communication avec les boîtiers sur le terrain. (<em>Documentation générée automatiquement à partir du code source</em>)</p>
"""
        for doc in api_docs:
            color = "#22c55e" if doc["method"] == "GET" else "#eab308"
            html += f"""
    <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; border-left: 4px solid {color};">
        <h3 style="margin-top: 0; display: flex; align-items: center; gap: 10px;">
            <code style="background: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em;">{doc['method']}</code>
            <strong>{doc['endpoint']}</strong>
        </h3>
        <p style="margin-bottom: 20px;">{doc['desc'].replace(chr(10), '<br>')}</p>
"""
            if doc['headers']:
                html += f"""
        <div style="margin-bottom: 15px;">
            <strong>Headers attendus :</strong>
            <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{doc['headers']}</pre>
        </div>"""
            if doc['usage']:
                html += f"""
        <div style="margin-bottom: 15px;">
            <strong>Exemple d'usage :</strong>
            <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{doc['usage']}</pre>
        </div>"""
            if doc['payload']:
                html += f"""
        <div style="margin-bottom: 15px;">
            <strong>Exemple de Payload JSON :</strong>
            <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{doc['payload']}</pre>
        </div>"""
            if doc['reponse']:
                html += f"""
        <div>
            <strong>Exemple de Réponse :</strong>
            <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px; font-size: 0.9em;">{doc['reponse']}</pre>
        </div>"""
                
            html += "</div>"

    html += """
</body>
</html>"""
    return html


# Import en effet de bord, apres definition de ui_app : chaque module
# fait `from web.ui import ui_app` puis `@ui_app.get(...)`/`@ui_app.post(...)`
# pour y enregistrer ses routes.
from web import stream as _stream  # noqa: E402,F401
from services import templates_maintenance as _templates_maintenance  # noqa: E402,F401
