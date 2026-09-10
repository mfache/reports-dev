"""Tests de la route /sync (coeur de la synchronisation boitier)."""
from __future__ import annotations

import json

from _helpers import call_wsgi


def test_sync_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/sync", method="POST",
        body=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"


def test_sync_avec_jeton_invalide_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/sync", method="POST",
        body=json.dumps({}),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer jeton-invalide-de-test",
        },
    )
    assert status == "401 Unauthorized"
