"""Bootstrap de l'UI web et façade de compatibilité.

L'instance ``ui_app`` est créée ici avant l'import des modules de routes :
les modules historiques (SSE, administration et maintenance) l'importent
encore depuis ``web.ui`` pour enregistrer leurs décorateurs Bottle.
"""
from __future__ import annotations

import json
from bottle import Bottle, request, response, static_file, TEMPLATE_PATH

from core.config import BASE_PATH
from core.paths import TEMPLATES_DIR, STATIC_DIR
from web.templating import view
from web.ui_point_labels import format_human_date


ui_app = Bottle()
TEMPLATE_PATH.append(str(TEMPLATES_DIR))

@ui_app.error(404)
def error404_ui(error):
    return view('404', title='404 - Introuvable')


@ui_app.get("/static/<filepath:path>")
def serve_static(filepath):
    return static_file(filepath, root=str(STATIC_DIR))


@ui_app.get("/favicon.ico")
def serve_favicon():
    return static_file("favicon.ico", root=str(STATIC_DIR))


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


# Imports en effet de bord, après définition de ui_app. L'ordre conserve
# l'enregistrement historique des routes et évite les imports circulaires.
from web import ui_chantiers as _ui_chantiers  # noqa: E402,F401
from web import ui_nodes as _ui_nodes  # noqa: E402,F401
from web import ui_dev as _ui_dev  # noqa: E402,F401
from web import stream as _stream  # noqa: E402,F401
from services import templates_maintenance as _templates_maintenance  # noqa: E402,F401
from web import admin_users as _admin_users  # noqa: E402,F401
from web import ui_rpi as _ui_rpi  # noqa: E402,F401
