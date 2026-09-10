"""Authentification des boitiers, enregistrement (manuel et automatique),
notifications de changement vers la flotte. Extrait d'api.py lors de la
refonte (voir CAHIER-DES-CHARGES-REFONTE.md).

Ce module sert aussi de socle partage par les autres modules `services/*` :
`authenticate_boitier` et `log_write` sont reutilises par chantiers.py,
sync.py, trends.py, logs.py et headscale.py.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import secrets
import urllib.error
import urllib.request

import pymysql
from bottle import request

from core.config import _ENV
from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok

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


