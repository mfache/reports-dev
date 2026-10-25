"""Tests de l'accès web aux boîtiers (services/acces_boitiers.py et
/rpi/authz) : sans session ni droit, nginx ne doit jamais recevoir d'amont."""
from __future__ import annotations

from unittest.mock import patch

from _helpers import call_wsgi

from services import acces_boitiers


class CurseurFactice:
    """Rejoue des réponses SQL dans l'ordre des requêtes."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)

    def execute(self, sql, params=None):
        self.courant = self.reponses.pop(0)

    def fetchall(self):
        return self.courant

    def fetchone(self):
        return self.courant[0] if self.courant else None


def _utilisateur(**champs):
    return {"id": 7, "ref": "ELE", "nom": "Électricien", "externe": 0,
            "mobile_valide": 1, "archive": 0, **champs}


def test_compte_sans_case_m_ne_voit_aucun_boitier():
    assert acces_boitiers.boitiers_autorises(CurseurFactice(), _utilisateur(mobile_valide=0)) == []


def test_compte_archive_ne_voit_aucun_boitier():
    assert acces_boitiers.boitiers_autorises(CurseurFactice(), _utilisateur(archive=1)) == []


def test_externe_sans_chantier_ne_voit_aucun_boitier():
    assert acces_boitiers.boitiers_autorises(CurseurFactice([]), _utilisateur(externe=1)) == []


def test_interne_valide_voit_les_boitiers():
    rpi = {"id": 2, "hostname": "rpi01", "last_sync_at": None, "chantier_id": 3, "chantier_ref": "H66"}
    assert acces_boitiers.boitiers_autorises(CurseurFactice([rpi]), _utilisateur()) == [rpi]


def _authz(wsgi_app, base_path, hostname, cookie="x=y"):
    """Appel tel que nginx le fait : X_RPI_HOST est un uwsgi_param (clé
    d'environ), pas un en-tête HTTP qu'un client pourrait forger."""
    from io import BytesIO
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": f"{base_path}/rpi/authz",
               "QUERY_STRING": "", "SERVER_NAME": "t", "SERVER_PORT": "80",
               "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.url_scheme": "http",
               "wsgi.input": BytesIO(b""), "wsgi.errors": None,
               "X_RPI_HOST": hostname, "HTTP_COOKIE": cookie}
    capture = {}
    b"".join(wsgi_app(environ, lambda s, h, e=None: capture.update(status=s, headers=dict(h))))
    return capture["status"], capture["headers"]


def test_authz_sans_session_renvoie_401(wsgi_app, base_path):
    with patch("web.ui_rpi.email_session_oauth2", return_value=None):
        status, headers = _authz(wsgi_app, base_path, "rpi01")
    assert status.startswith("401")
    assert "X-Rpi-Upstream" not in headers


def test_authz_boitier_non_autorise_renvoie_403(wsgi_app, base_path):
    with patch("web.ui_rpi.email_session_oauth2", return_value="inconnu@exemple.be"), \
         patch("web.ui_rpi.ips_tailscale", return_value={"rpi01": "100.64.0.5"}):
        status, headers = _authz(wsgi_app, base_path, "rpi01")
    assert status.startswith("403")
    assert "X-Rpi-Upstream" not in headers


def test_authz_autorise_donne_l_amont_tailscale(wsgi_app, base_path):
    with patch("web.ui_rpi.email_session_oauth2", return_value="marc@fache.be"), \
         patch("web.ui_rpi.utilisateur_par_email", return_value=_utilisateur()), \
         patch("web.ui_rpi.boitiers_autorises", return_value=[{"hostname": "rpi01"}]), \
         patch("web.ui_rpi.ips_tailscale", return_value={"rpi01": "100.64.0.5"}):
        status, headers = _authz(wsgi_app, base_path, "rpi01")
    assert status.startswith("200")
    assert headers["X-Rpi-Upstream"] == "100.64.0.5"


def test_authz_hostname_invalide_renvoie_403(wsgi_app, base_path):
    status, headers, _ = call_wsgi(wsgi_app, f"{base_path}/rpi/authz")
    assert status.startswith("403")
    assert "X-Rpi-Upstream" not in headers


def test_ip_hors_tailnet_jamais_retenue_comme_amont():
    noeuds = [{"name": "rpi99", "given_name": "rpi99", "ip_addresses": ["37.184.96.104"]},
              {"name": "rpi01", "given_name": "rpi01", "ip_addresses": ["fd7a:115c:a1e0::5", "100.64.0.5"]}]
    acces_boitiers._cache_ips["expire"] = 0
    with patch("services.acces_boitiers._run_headscale", return_value=noeuds):
        ips = acces_boitiers.ips_tailscale()
    acces_boitiers._cache_ips["expire"] = 0
    assert ips == {"rpi01": "100.64.0.5"}
