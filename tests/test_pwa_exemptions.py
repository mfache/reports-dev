"""sw.js et manifest.json doivent rester accessibles sans session (cf.
incident du 10 septembre : le Service Worker d'une PWA deja installee
verifie sw.js en tache de fond independamment de la navigation, et
ecrasait le cookie CSRF du flux OAuth quand nginx protegeait cette
route par auth_request -- voir NOTES-evolutions.md). Ces routes elles-
memes ne sont jamais protegees par l'application (la protection est du
ressort de nginx), donc ce test verifie surtout qu'elles repondent et
qu'elles servent bien les fichiers de CETTE instance.
"""
from __future__ import annotations

from _helpers import call_wsgi


def test_sw_js_repond(wsgi_app, base_path):
    status, headers, body = call_wsgi(wsgi_app, f"{base_path}/sw.js")
    assert status == "200 OK"
    assert len(body) > 0


def test_sw_js_service_worker_allowed_suit_base_path(wsgi_app, base_path):
    """Non-regression : cet en-tete etait fige a '/reports/' avant la
    refonte, ce qui aurait empeche le Service Worker de dev de
    s'enregistrer sur le bon scope."""
    status, headers, _ = call_wsgi(wsgi_app, f"{base_path}/sw.js")
    assert status == "200 OK"
    assert headers.get("Service-Worker-Allowed") == f"{base_path}/"


def test_manifest_json_repond(wsgi_app, base_path):
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/manifest.json")
    assert status == "200 OK"
    assert len(body) > 0
