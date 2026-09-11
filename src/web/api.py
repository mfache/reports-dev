"""Point d'entree de l'API de flotte `reports` : cree `api_app`, les
gestionnaires d'erreur et les routes transverses (`/usage`, interception
`/version` et `/*/usage`), puis importe chaque module `services/*` pour
que ses routes s'enregistrent sur `api_app` (effet de bord de l'import).

Sur le modele rpinode/src/web : le decoupage par domaine metier vit dans
`services/`, ce module se contente d'assembler l'application (voir
CAHIER-DES-CHARGES-REFONTE.md).

Ordre d'import important : `api_app` doit exister avant que les modules
`services/*` ne fassent `from web.api import api_app` pour y enregistrer
leurs routes.
"""
from __future__ import annotations

import json

from bottle import Bottle, HTTPResponse, request, response
import paho.mqtt.publish as mqtt_publish
import uuid

from web.responses import json_error, json_ok

api_app = Bottle()

API_VERSION = "1.2.1"

# Chaque import ci-dessous enregistre ses routes sur api_app par effet de
# bord (chaque module services/* fait `from web.api import api_app` puis
# `@api_app.get(...)`/`@api_app.post(...)`). L'ordre entre domaines n'a pas
# d'importance, seules les dependances internes a services/ en ont
# (sync.py importe chantiers.py, qui importe fleet.py).
from services import fleet as _fleet  # noqa: E402,F401
from services import chantiers as _chantiers  # noqa: E402,F401
from services import sync as _sync  # noqa: E402,F401
from services import trends as _trends  # noqa: E402,F401
from services import logs as _logs  # noqa: E402,F401
from services import headscale as _headscale  # noqa: E402,F401


@api_app.get("/usage")
def global_usage():
    """
    Renvoie la liste des API disponibles et leur usage.
    """
    # Si on appelle directement /reports/api/usage, on n'a pas de "base_path"
    # L'intercepteur va chercher "" ou "/", ce qui n'existe pas ou ne donne pas ce qu'on veut.
    # On gère donc explicitement /reports/api/usage ici.

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

@api_app.post("/sse/sync")
def sse_sync_points():
    """
    Synchronise les points suivis par un client SSE.
    Le payload contient l'UUID du client et les points ajoutés/retirés.
    """
    data = request.json or {}
    client_uuid = data.get("uuid")
    added = data.get("added", [])
    removed = data.get("removed", [])

    if not client_uuid:
        return json_error(400, "UUID manquant")

    payload = {
        "uuid": client_uuid,
        "added": added,
        "removed": removed
    }

    try:
        mqtt_publish.single(
            "reports/sse/requests",
            json.dumps(payload),
            hostname="127.0.0.1"
        )
    except Exception as e:
        return json_error(500, f"Erreur MQTT: {str(e)}")

    return json_ok({"status": "ok"})

@api_app.error(404)
def error404_api(error):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": "Endpoint introuvable (404)"}, ensure_ascii=False)

@api_app.error(500)
def error500_api(error):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": "Erreur interne (500)"}, ensure_ascii=False)
