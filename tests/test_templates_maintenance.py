"""Tests de la maintenance des templates Modbus partages (page UI)."""
from __future__ import annotations

from _helpers import call_wsgi


def test_maintenance_templates_repond(wsgi_app, base_path):
    status, _, _ = call_wsgi(wsgi_app, f"{base_path}/maintenance/templates")
    assert status == "200 OK"


def test_diff_data_sans_parametres_est_refuse(wsgi_app, base_path):
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/maintenance/templates/diff-data")
    assert status == "400 Bad Request"
    assert "requises" in body


def test_toggle_deprecate_sans_revision_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/maintenance/templates/toggle_deprecate", method="POST",
        body="{}", headers={"Content-Type": "application/json"},
    )
    assert status == "400 Bad Request"
