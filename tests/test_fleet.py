"""Tests du service fleet : ping, register (+ conflit), register/auto."""
from __future__ import annotations

import json
import uuid

from _helpers import call_wsgi

JOIN_SECRET = "dev-only-secret-ne-jamais-utiliser-en-prod"


def test_ping_sans_authentification(wsgi_app, base_path):
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/api/ping")
    assert status == "200 OK"
    data = json.loads(body)
    assert data["ok"] is True
    assert "time" in data


def test_register_sans_secret_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/register", method="POST",
        body=json.dumps({"hostname": "test-refuse"}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "403 Forbidden"


def test_register_avec_secret_cree_puis_refuse_le_doublon(wsgi_app, base_path):
    hostname = f"test-{uuid.uuid4().hex[:12]}"

    status, _, body = call_wsgi(
        wsgi_app, f"{base_path}/api/register", method="POST",
        body=json.dumps({"hostname": hostname}),
        headers={"Content-Type": "application/json", "X-Join-Secret": JOIN_SECRET},
    )
    assert status == "200 OK"
    data = json.loads(body)
    assert data["ok"] is True
    assert data["token"]

    # Meme hostname : refuse (409), pas de jeton reemis.
    status2, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/register", method="POST",
        body=json.dumps({"hostname": hostname}),
        headers={"Content-Type": "application/json", "X-Join-Secret": JOIN_SECRET},
    )
    assert status2 == "409 Conflict"


def test_register_auto_sans_secret_est_refuse(wsgi_app, base_path):
    status, _, _ = call_wsgi(
        wsgi_app, f"{base_path}/api/register/auto", method="POST",
        body=json.dumps({"cpu_serial": "test-cpu-serial"}),
        headers={"Content-Type": "application/json"},
    )
    assert status == "403 Forbidden"


def test_register_auto_avec_secret_attribue_un_hostname_rpiNN(wsgi_app, base_path):
    # Format realiste (numero de serie CPU du Raspberry Pi : 16 caracteres
    # hexadecimaux), la colonne cpu_serial est un varchar(32).
    cpu_serial = uuid.uuid4().hex[:16]
    status, _, body = call_wsgi(
        wsgi_app, f"{base_path}/api/register/auto", method="POST",
        body=json.dumps({"cpu_serial": cpu_serial}),
        headers={"Content-Type": "application/json", "X-Join-Secret": JOIN_SECRET},
    )
    assert status == "200 OK"
    data = json.loads(body)
    assert data["ok"] is True
    assert data["hostname"].startswith("rpi")
