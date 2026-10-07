"""Configuration centralisee de `reports`.

Isole ce qui etait auparavant duplique/en dur entre `db.py` et `app.py` :
le fichier d'environnement a lire (secrets DB) et le prefixe de montage
WSGI. Sur le modele de `rpinode/src/core/config.py` (voir
CAHIER-DES-CHARGES-REFONTE.md).

Les deux valeurs sont surchargeables via l'environnement uwsgi
(`reports-dev.ini` les fixe a `/etc/boitier-fleet/db-dev.env` et
`/reports-dev` ; `reports.ini`, en production, ne les fixe pas et
conserve donc le comportement historique).
"""
from __future__ import annotations

import os
from urllib.parse import quote

DB_ENV_FILE = os.environ.get("DB_ENV_FILE", "/etc/boitier-fleet/db.env")

BASE_PATH = os.environ.get("REPORTS_BASE_PATH", "/reports")

# Domaine public et tenant Azure AD/Entra ID, pour construire l'URL de
# deconnexion complete (voir build_logout_url ci-dessous). Meme domaine
# que celui deja code en dur dans services/headscale.py.
APP_DOMAIN = "https://docs.deltathermic.be"
AZURE_TENANT_ID = "6f5a8612-d079-4c00-89fd-3df64e4a55b1"


def build_logout_url() -> str:
    """URL du bouton "Deconnexion" : purge d'abord le cookie oauth2-proxy
    local (`/oauth2/sign_out`), puis redirige vers le endpoint de
    deconnexion Azure AD (`end_session_endpoint`) pour fermer aussi la
    session SSO cote Microsoft. Sans ce 2e saut, revenir sur l'app
    reconnecte silencieusement via le SSO toujours actif (constate le
    7 octobre : "Deconnexion" ramenait a l'accueil deja authentifie).

    Necessite `whitelist_domains = [ "login.microsoftonline.com" ]` dans
    `/etc/oauth2-proxy/oauth2-proxy.cfg` (sinon oauth2-proxy ignore le
    `rd` externe et retombe sur "/").
    """
    post_logout_redirect_uri = f"{APP_DOMAIN}{BASE_PATH}/"
    azure_logout_url = (
        f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={quote(post_logout_redirect_uri, safe='')}"
    )
    return f"/oauth2/sign_out?rd={quote(azure_logout_url, safe='')}"


def _read_env(path: str) -> dict:
    """Lit un fichier `CLE=valeur` simple (mêmes règles que l'ancien
    `db.py`) : lignes vides et commentaires ignorés, guillemets optionnels
    autour de la valeur. Ne lève jamais si le fichier est absent ou
    illisible (comportement historique conservé)."""
    env: dict[str, str] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


_ENV = _read_env(DB_ENV_FILE)
