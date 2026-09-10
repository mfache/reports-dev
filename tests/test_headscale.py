"""Tests du service headscale : enrolement et approbation de routes
exigent un jeton boitier valide (n'appellent jamais le binaire
`headscale` reel sans authentification prealable)."""
from __future__ import annotations

import json

from _helpers import call_wsgi


def test_headscale_enroll_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/api/headscale/enroll", method="POST")
    assert status == "401 Unauthorized"


def test_headscale_routes_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/headscale/routes", method="POST",
        body=json.dumps({"routes": []}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"
