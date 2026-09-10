"""Tests du service trends : trends, points-config, suppression de colonne."""
from __future__ import annotations

import json

from _helpers import call_wsgi


def test_trends_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/trends", method="POST",
        body=json.dumps({"trends": []}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"


def test_points_config_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/points-config", method="POST",
        body=json.dumps({"points": []}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"


def test_table_column_delete_sans_jeton_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/table/column/delete", method="POST",
        body=json.dumps({"table_id": "x", "column_key": "y"}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "401 Unauthorized"
