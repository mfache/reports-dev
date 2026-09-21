"""Developer-only routes: SQL console, database sync, simulator and deployment."""
from __future__ import annotations

import json
import os
import signal
import subprocess

from bottle import request, response

from core.config import BASE_PATH
from core.database import get_db
from web.templating import get_current_user, view
from web.ui import ui_app

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
                    cols = cur.fetchall()
                    cur.execute(f"SELECT count(*) as count FROM {table}")
                    count = cur.fetchone()['count']
                    tables_info[table] = {'cols': cols, 'count': count}
        finally:
            db.close()

        # Génération du code Mermaid pour le diagramme Entité-Association
        mermaid_code = "erDiagram\n"
        for fk in foreign_keys:
            mermaid_code += f"    {fk['REFERENCED_TABLE_NAME']} ||--o{{ {fk['TABLE_NAME']} : \"{fk['COLUMN_NAME']}\"\n"

        for table, info in tables_info.items():
            mermaid_code += f"    {table} {{\n"
            for col in info['cols']:
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


