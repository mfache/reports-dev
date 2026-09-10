"""Tests du service chantiers : toutes les routes exigent un jeton
boitier valide (Authorization: Bearer ...)."""
from __future__ import annotations

import json

from _helpers import call_wsgi


def test_chantiers_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/api/chantiers")
    assert status == "401 Unauthorized"


def test_chantier_net_profiles_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/api/chantier/1/net_profiles")
    assert status == "401 Unauthorized"


def test_chantier_antennes_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/api/chantier/1/antennes")
    assert status == "401 Unauthorized"


def test_chantier_rename_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/chantier/rename", method="POST",
        body=json.dumps({"chantier_id": 1, "ref": "Test"}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"
