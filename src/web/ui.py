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

from bottle import Bottle, request, response, static_file, TEMPLATE_PATH

from core.database import get_db
from core.config import BASE_PATH
from core.paths import TEMPLATES_DIR, STATIC_DIR
from web.templating import render, view, get_current_user

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
    return view('404', title='404 - Introuvable')


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
            data["name"] = "Graphique Deltathermic"
            data["short_name"] = "DT Graph"
            response.content_type = "application/manifest+json"
            return json.dumps(data)
        except Exception:
            pass
    return static_file("manifest.json", root=str(STATIC_DIR), mimetype="application/manifest+json")


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

    return view('chantier',
                title=f"Chantier {chantier['ref']} - Deltathermic",
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

    return render('chart_view',
                chantier=chantier,
                chart_param_json=json.dumps(chart_param),
                manifest_url=manifest_url)



@ui_app.get("/nodes")
def nodes_view():
    db = get_db()
    try:
        with db.cursor() as cur:
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

    return view('nodes',
                title='Nodes - Deltathermic',
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


@ui_app.post("/dev/sync-db")
def dev_sync_db():
    if BASE_PATH == "/reports":
        response.status = 403
        return {"error": "Interdit en production."}
    
    import subprocess
    try:
        cmd = "sudo mysqldump --single-transaction --routines --triggers dt | sudo mysql dt_dev"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode != 0:
            return {"error": f"Erreur de synchronisation : {res.stderr}"}
            
        return {"status": "ok", "message": "La base de données de développement (dt_dev) a été synchronisée depuis la production."}
    except Exception as e:
        return {"error": f"Exception : {str(e)}"}


# --- Déploiement du bac à sable vers la production -----------------------
# Flux réel documenté dans OPERATIONS.md (docs-infra) : `/var/www/reports`
# est la vraie production (servie par l'app uwsgi `reports`) ; `docs-infra`
# n'est qu'une armoire à archives qui documente l'état de la prod *après*
# coup, ce n'est PAS un mécanisme de déploiement. L'ordre correct est donc :
#   1) commit local (reports-dev, historique perso)
#   2) rsync reports-dev -> /var/www/reports (le vrai déploiement)
#   3) rechargement du worker uwsgi de prod (jamais `service`/`systemctl`)
#   4) rsync /var/www/reports -> docs-infra (archive de l'état réel déployé)
#   5) commit + push (docs-infra)
# Les dépôts Git et la clé SSH de déploiement appartiennent à l'utilisateur
# système `marc` (et non à l'utilisateur uwsgi `mariadb`) : chaque commande
# de fichier/Git est donc exécutée via `sudo -u marc`, autorisé sans mot de
# passe sur ce bac à sable.
REPORTS_DEV_DIR = "/opt/reports-dev"
PROD_DIR = "/var/www/reports"
PROD_PID_FILE = "/run/uwsgi/app/reports/pid"
DOCS_INFRA_DIR = "/opt/docs-infra"
DOCS_INFRA_REPORTS_SUBDIR = "var/www/reports"
DEPLOY_GIT_USER = "marc"
UWSGI_DEV_INI = "/etc/uwsgi/apps-enabled/reports-dev.ini"
UWSGI_PROD_INI = "/etc/uwsgi/apps-enabled/reports.ini"


def _run_as_marc(args, cwd=None):
    import subprocess
    import os as _os
    cmd = ["sudo", "-u", DEPLOY_GIT_USER, "-H"] + args
    env = _os.environ.copy()
    env["GIT_EDITOR"] = "true"
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def _comparer_configs_uwsgi():
    """Compare reports-dev.ini et reports.ini pour detecter une derive de
    config (ex: incident du 12/09/2026 : pythonpath src/ ajoute cote dev
    mais jamais reporte cote prod -> ModuleNotFoundError en prod). Les
    differences de chemins/socket/venv attendues entre les deux environnements
    sont normalisees avant comparaison ; seules les differences structurelles
    (directives manquantes ou en trop) remontent."""
    try:
        with open(UWSGI_DEV_INI) as f:
            dev_lignes = f.read().splitlines()
        with open(UWSGI_PROD_INI) as f:
            prod_lignes = f.read().splitlines()
    except OSError as e:
        return {"erreur": str(e), "manquant_en_prod": [], "en_trop_en_prod": []}

    import re

    def normalise(lignes):
        resultat = []
        for ligne in lignes:
            stripped = ligne.strip()
            if not stripped:
                continue
            # Ces variables d'environnement n'existent volontairement qu'en dev.
            if stripped.startswith("env = REPORTS_BASE_PATH") or stripped.startswith("env = DB_ENV_FILE"):
                continue
            stripped = stripped.replace(REPORTS_DEV_DIR, PROD_DIR).replace("reports-dev", "reports")
            # Espaces multiples cosmetiques (ex: "chdir =  /path") ignores.
            stripped = re.sub(r"\s+", " ", stripped)
            resultat.append(stripped)
        return resultat

    dev_normalise = set(normalise(dev_lignes))
    prod_normalise = set(normalise(prod_lignes))

    return {
        "erreur": None,
        "manquant_en_prod": sorted(dev_normalise - prod_normalise),
        "en_trop_en_prod": sorted(prod_normalise - dev_normalise),
    }


def _reload_prod_worker():
    import subprocess
    try:
        with open(PROD_PID_FILE) as f:
            pid = f.read().strip()
    except OSError as e:
        return subprocess.CompletedProcess(args=["read-pid"], returncode=1, stdout="", stderr=str(e))
    return subprocess.run(["sudo", "kill", "-HUP", pid], capture_output=True, text=True)


def _require_deploy_access():
    if BASE_PATH == "/reports":
        response.status = 403
        return {"error": "Interdit en production."}
    current_user = get_current_user()
    if not current_user or not current_user.get('is_root'):
        response.status = 403
        return {"error": "Accès refusé."}
    return None


@ui_app.post("/dev/deploy")
def dev_deploy():
    denied = _require_deploy_access()
    if denied:
        return denied

    message = (request.json or {}).get("message", "").strip()
    if not message:
        return {"error": "Un message de commit est requis."}

    warnings = []
    cfg = _comparer_configs_uwsgi()
    if cfg["erreur"]:
        warnings.append(f"Impossible de comparer reports.ini et reports-dev.ini : {cfg['erreur']}")
    elif cfg["manquant_en_prod"] or cfg["en_trop_en_prod"]:
        warnings.append(
            "La config uWSGI de production (reports.ini) semble diverger de celle de dev "
            "(reports-dev.ini), au-dela des differences de chemins attendues. "
            "Ce deploiement NE modifie PAS ce fichier : verifiez/adaptez-le manuellement "
            "si necessaire (voir l'apercu de l'onglet Deploiement pour le detail)."
        )

    steps = []

    def commit_ok(res):
        return res.returncode == 0 or "nothing to commit" in ((res.stdout or "") + (res.stderr or "")).lower()

    def add_step(label, res, ok):
        steps.append({"label": label, "ok": ok, "output": ((res.stdout or "") + (res.stderr or "")).strip()})

    # 1. Commit local dans le bac à sable (reports-dev), purement informatif
    _run_as_marc(["git", "add", "-A"], cwd=REPORTS_DEV_DIR)
    r = _run_as_marc(["git", "commit", "-m", message], cwd=REPORTS_DEV_DIR)
    ok = commit_ok(r)
    add_step("Commit local (reports-dev)", r, ok)
    if not ok:
        return {"error": "Échec du commit local.", "steps": steps}

    # 2. Le vrai déploiement : copie vers /var/www/reports (production)
    r = _run_as_marc([
        "rsync", "-av", "--delete",
        "--exclude=.git", "--exclude=__pycache__",
        f"{REPORTS_DEV_DIR}/", f"{PROD_DIR}/",
    ])
    ok = r.returncode == 0
    add_step("Déploiement (rsync) vers /var/www/reports (production)", r, ok)
    if not ok:
        return {"error": "Échec du déploiement vers la production.", "steps": steps}

    # 3. Rechargement du worker uwsgi de production (jamais service/systemctl)
    r = _reload_prod_worker()
    ok = r.returncode == 0
    add_step("Rechargement du worker uwsgi de production", r, ok)
    if not ok:
        return {"error": "Échec du rechargement de la production.", "steps": steps}

    # 4. Archivage de l'état réel de la prod vers docs-infra (backup Git)
    r = _run_as_marc([
        "rsync", "-av", "--delete",
        "--exclude=.git", "--exclude=__pycache__",
        f"{PROD_DIR}/", f"{DOCS_INFRA_DIR}/{DOCS_INFRA_REPORTS_SUBDIR}/",
    ])
    ok = r.returncode == 0
    add_step("Archivage (rsync) de la prod vers docs-infra", r, ok)
    if not ok:
        return {"error": "Échec de l'archivage vers docs-infra.", "steps": steps}

    # 5. Commit + Push côté dépôt officiel (docs-infra)
    _run_as_marc(["git", "add", DOCS_INFRA_REPORTS_SUBDIR], cwd=DOCS_INFRA_DIR)
    r = _run_as_marc(["git", "commit", "-m", message], cwd=DOCS_INFRA_DIR)
    ok = commit_ok(r)
    add_step("Commit (docs-infra)", r, ok)
    if not ok:
        return {"error": "Échec du commit dans docs-infra.", "steps": steps}

    r = _run_as_marc(["git", "push"], cwd=DOCS_INFRA_DIR)
    ok = r.returncode == 0
    add_step("Push GitHub", r, ok)
    if not ok:
        return {"error": "Échec du push.", "steps": steps}

    return {"status": "ok", "message": "Déploiement effectué en production et archivé avec succès.", "steps": steps, "warnings": warnings}



import subprocess
import os
import signal

SIMULATOR_PID_FILE = "/tmp/reports_simulator.pid"

def get_simulator_pid():
    if os.path.exists(SIMULATOR_PID_FILE):
        try:
            with open(SIMULATOR_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return pid
        except (ValueError, OSError):
            os.remove(SIMULATOR_PID_FILE)
    return None

@ui_app.post("/dev/simulator/toggle")
def toggle_simulator():
    pid = get_simulator_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        if os.path.exists(SIMULATOR_PID_FILE):
            os.remove(SIMULATOR_PID_FILE)
        return {"status": "stopped"}
    else:
        import sys
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools', 'simulateur_ui.py')
        
        # Transmet les variables d'environnement actuelles du processus uWSGI
        # (incluant potentiellement les identifiants DB déjà décodés ou le DB_ENV_FILE autorisé)
        env = os.environ.copy()
        
        proc = subprocess.Popen([sys.executable, script_path], env=env)
        with open(SIMULATOR_PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        return {"status": "started"}

@ui_app.get("/dev/simulator/status")
def simulator_status():
    return {"status": "started" if get_simulator_pid() else "stopped"}

@ui_app.get("/dev")
def dev():
    tab = request.query.get("tab", "sql")
    data = {"tab": tab}
    
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
            
        data.update({
            "tables": tables,
            "tables_info": tables_info,
            "mermaid_code": mermaid_code
        })
            
    elif tab == "api":
        from web.api import api_app
        api_docs = []
        for route in api_app.routes:
            obj = route.callback
            if not (obj and hasattr(obj, '__doc__') and obj.__doc__):
                continue
            doc = obj.__doc__.strip()
            if "Réponse:" in doc:
                # Extraction basique des différentes parties
                desc = doc.split("Usage:")[0].split("Headers:")[0].split("Payload:")[0].strip()
                usage = doc.split("Usage:")[1].split("Réponse:")[0].strip() if "Usage:" in doc else ""
                payload = doc.split("Payload:")[1].split("Réponse:")[0].strip() if "Payload:" in doc else ""
                if payload and "Headers:" in payload:
                    payload = payload.split("Headers:")[0].strip()
                headers = doc.split("Headers:")[1].split("Payload:")[0].split("Usage:")[0].split("Réponse:")[0].strip() if "Headers:" in doc else ""
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
        data["api_docs"] = api_docs

    elif tab == "env":
        import os
        data["env_vars"] = sorted(os.environ.items())
        # Ajout des infos d'identité détectées
        data["auth_email"] = request.environ.get('X_EMAIL', 'Non détecté')
        data["auth_user"] = request.environ.get('X_USER', 'Non détecté')

    elif tab == "deploy":
        if BASE_PATH == "/reports":
            data["git_status_error"] = "Cet outil n'est disponible que depuis reports-dev."
            data["git_status_lignes"] = []
            data["prod_diff_error"] = None
            data["prod_diff_lignes"] = []
            data["uwsgi_cfg"] = {"erreur": None, "manquant_en_prod": [], "en_trop_en_prod": []}
        else:
            res = _run_as_marc(["git", "status", "--porcelain"], cwd=REPORTS_DEV_DIR)
            lignes = [l for l in (res.stdout or "").splitlines() if l.strip()]
            data["git_status_lignes"] = lignes
            data["git_status_error"] = res.stderr.strip() if res.returncode != 0 else None

            # Aperçu de ce que le déploiement écrirait réellement dans
            # /var/www/reports (la vraie production), en mode dry-run.
            res2 = _run_as_marc([
                "rsync", "-avn", "--delete",
                "--exclude=.git", "--exclude=__pycache__",
                f"{REPORTS_DEV_DIR}/", f"{PROD_DIR}/",
            ])
            prod_lignes = [
                l for l in (res2.stdout or "").splitlines()
                if l.strip() and l not in ("sending incremental file list", "./") and not l.startswith(("sent ", "total size"))
            ]
            data["prod_diff_lignes"] = prod_lignes
            data["prod_diff_error"] = res2.stderr.strip() if res2.returncode != 0 else None

            # Vérification de la dérive de config uWSGI (cf. incident du
            # 12/09/2026 : pythonpath src/ manquant en prod).
            data["uwsgi_cfg"] = _comparer_configs_uwsgi()

    return view('dev', title='Espace Développeur', **data)


# Import en effet de bord, apres definition de ui_app : chaque module
# fait `from web.ui import ui_app` puis `@ui_app.get(...)`/`@ui_app.post(...)`
# pour y enregistrer ses routes.
from web import stream as _stream  # noqa: E402,F401
from services import templates_maintenance as _templates_maintenance  # noqa: E402,F401
from web import admin_users as _admin_users  # noqa: E402,F401
