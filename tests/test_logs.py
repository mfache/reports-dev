"""Tests du service logs : POST/GET exigent un jeton boitier valide."""
from __future__ import annotations

import json

from _helpers import call_wsgi


def test_post_logs_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/logs", method="POST",
        body=json.dumps({"logs": []}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"


def test_get_logs_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/api/logs")
    assert status == "401 Unauthorized"
