"""Enregistrement et consultation des logs remontes par les boitiers.
Extrait d'api.py lors de la refonte (voir CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import datetime
import gzip
import json

from bottle import request

from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok
from services.fleet import authenticate_boitier

@api_app.post("/logs")
def post_logs():
    """
    Enregistre des logs envoyés par un boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "logs": [
                {
                    "level": "ERROR",
                    "module": "services.tracker",
                    "message": "Erreur SQL",
                    "timestamp": "2023-10-25T14:30:00"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "inserted": 1
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
            logs = data.get("logs", [])
            if not logs:
                return json_ok({"inserted": 0})

            inserted = 0
            for log_entry in logs:
                level = str(log_entry.get("level", "INFO"))[:16]
                module = str(log_entry.get("module", "unknown"))[:128]
                message = str(log_entry.get("message", ""))
                timestamp = log_entry.get("timestamp")
                git_version = str(log_entry.get("git_version", ""))[:64]
                chantier_id = boitier.get("chantier_id")

                if not timestamp:
                    timestamp = datetime.datetime.utcnow().isoformat()

                cur.execute(
                    "INSERT INTO boitier_logs (boitier_id, chantier_id, level, module, message, timestamp, git_version) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (boitier["id"], chantier_id, level, module, message, timestamp, git_version)
                )
                inserted += 1

        return json_ok({"inserted": inserted})
    finally:
        db.close()


@api_app.get("/logs")
def get_logs():
    """
    Récupère les derniers logs enregistrés par le boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Query params optionnels:
        limit: Nombre de logs à retourner (défaut 50)
        level: Filtrer par niveau (ex: ERROR)

    Réponse:
        {
            "ok": true,
            "logs": [...]
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            limit = int(request.query.get("limit", 50))
            level = request.query.get("level")

            query = "SELECT * FROM boitier_logs WHERE boitier_id = %s"
            params = [boitier["id"]]

            if level:
                query += " AND level = %s"
                params.append(level)

            query += " ORDER BY id DESC LIMIT %s"
            params.append(limit)

            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return json_ok({"logs": rows})
    finally:
        db.close()
