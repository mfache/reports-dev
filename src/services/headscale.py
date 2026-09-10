"""Auto-enrolement des boitiers (hostname assigne par le serveur) et
integration Headscale (voir rpinode: docs/integrations/HEADSCALE_AUTO_ENROLL.md).
Ajoute le 8 septembre 2026, extrait d'api.py lors de la refonte (voir
CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import json
import subprocess
import sys

from bottle import request

from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok
from services.fleet import authenticate_boitier, log_write

HEADSCALE_BIN = "headscale"
HEADSCALE_USER_ID = "1"  # utilisateur Headscale "delta"
HEADSCALE_LOGIN_SERVER = "https://docs.deltathermic.be"
HEADSCALE_FLEET_TAG = "tag:fleet"  # pose automatiquement sur chaque noeud boitier

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
