"""Non-regression directe de l'incident du 10 septembre 2026 (matin) :
apres reconstruction d'app.py, seule l'API repondait, l'UI (ui_app)
n'etait montee nulle part et renvoyait un 404 apres authentification --
jamais remarque a l'epoque faute de test de bout en bout (voir
NOTES-evolutions.md)."""
from _helpers import call_wsgi


def test_ui_root_repond(wsgi_app, base_path):
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/")
    assert status == "200 OK"
    assert "Utilisateur introuvable" not in body


def test_api_usage_repond(wsgi_app, base_path):
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/api/usage")
    assert status == "200 OK"
    assert '"ok": true' in body


def test_api_et_ui_sont_deux_montages_distincts(wsgi_app, base_path):
    """/api doit aller vers l'API (qui repond), pas vers l'UI (qui
    renverrait son propre 404 HTML sur un endpoint API inconnu)."""
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/api/ping")
    assert status == "200 OK"
    assert '"ok": true' in body


def test_nombre_de_routes_api_inchange(wsgi_app):
    import app as app_module
    # Garde-fou contre une perte accidentelle de route lors d'un futur
    # refactor : 16 routes au moment de l'eclatement d'api.py (10/09/2026).
    assert len(app_module.api_app.routes) == 16


def test_nombre_de_routes_ui_inchange(wsgi_app):
    import app as app_module
    # Idem pour ui_app : 18 routes au moment de l'eclatement d'ui.py.
    assert len(app_module.ui_app.routes) == 18
