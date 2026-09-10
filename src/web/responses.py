"""Helpers de formatage des reponses JSON, partages par toutes les routes
de l'API. Extrait d'api.py lors de la refonte (voir
CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import json

from bottle import response


def json_error(status, message):
    response.status = status
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def json_ok(payload):
    response.content_type = "application/json; charset=utf-8"
    return json.dumps({"ok": True, **payload}, ensure_ascii=False, default=str)
