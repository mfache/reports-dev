"""Accès web aux interfaces des boîtiers à travers docs, sans Tailscale ni
certificat interne côté navigateur (ajouté le 25 octobre 2026).

Chaîne : navigateur -> nginx (``/rpi/<hostname>/``) -> ``auth_request`` vers
``/rpi/authz`` (web/ui_rpi.py, qui s'appuie sur ce module) -> proxy vers
l'IP Tailscale du boîtier, port 8081. Le boîtier reçoit
``X-Forwarded-Prefix`` et construit ses URL en conséquence (rpinode :
docs/operations/PREFIXE_REVERSE_PROXY.md).

Règle d'accès : la même que l'application mobile (services/mobile.py),
pour n'en avoir qu'une : compte non archivé ET ``mobile_valide`` (case
« M » de /admin/utilisateurs), et, pour un compte ``externe``, uniquement
les boîtiers de ses chantiers (``utilisateurs_chantiers``).
"""
from __future__ import annotations

import ipaddress
import re
import sys
import time
import urllib.error
import urllib.request

from services.headscale import _run_headscale

#: Seules des adresses du tailnet peuvent servir d'amont au proxy : une IP
#: publique (``boitier_registre.last_ip``) ne doit jamais y arriver.
TAILNET = ipaddress.ip_network("100.64.0.0/10")

#: oauth2-proxy (Azure) : sa route /oauth2/auth répond 202 + l'email si le
#: cookie de session est valide. Appelé par le code car nginx n'exécute pas
#: un ``auth_request`` à l'intérieur d'un autre (phase d'accès sautée dans
#: les sous-requêtes).
OAUTH2_AUTH_URL = "http://127.0.0.1:4180/oauth2/auth"

HOSTNAME_VALIDE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")

_DUREE_CACHE_IPS = 60
_cache_ips: dict = {"expire": 0.0, "ips": {}}


def email_session_oauth2(cookie_header: str | None) -> str | None:
    """Email de la session oauth2-proxy portée par ces cookies, ou None."""
    if not cookie_header:
        return None
    req = urllib.request.Request(OAUTH2_AUTH_URL, headers={"Cookie": cookie_header})
    try:
        with urllib.request.urlopen(req, timeout=5) as rep:
            if rep.status != 202:
                return None
            return (rep.headers.get("X-Auth-Request-Email") or "").strip().lower() or None
    except urllib.error.HTTPError:
        return None  # 401 : pas (ou plus) de session
    except OSError as echec:
        print(f"[acces_boitiers] oauth2-proxy injoignable : {echec}", file=sys.stderr)
        return None


def ips_tailscale() -> dict[str, str]:
    """hostname -> IPv4 Tailscale, d'après headscale (cache de 60 s)."""
    maintenant = time.monotonic()
    if maintenant < _cache_ips["expire"]:
        return _cache_ips["ips"]
    ips: dict[str, str] = {}
    try:
        for noeud in _run_headscale(["nodes", "list"]):
            ipv4 = next((a for a in noeud.get("ip_addresses") or []
                         if ipaddress.ip_address(a).version == 4
                         and ipaddress.ip_address(a) in TAILNET), None)
            if not ipv4:
                continue
            for nom in {noeud.get("name"), noeud.get("given_name")} - {None, ""}:
                ips[nom] = ipv4
    except Exception as echec:  # noqa: BLE001 - un headscale en panne ne doit pas casser la page
        print(f"[acces_boitiers] lecture headscale impossible : {echec}", file=sys.stderr)
        return _cache_ips["ips"]
    _cache_ips.update(expire=maintenant + _DUREE_CACHE_IPS, ips=ips)
    return ips


def utilisateur_par_email(cur, email: str) -> dict | None:
    cur.execute(
        """
        SELECT u.id, u.ref, u.nom, u.externe, u.mobile_valide, u.archive
        FROM utilisateurs u
        JOIN utilisateurs_emails e ON e.utilisateur_id = u.id
        WHERE LOWER(e.email) = %s
        """,
        (email.lower(),),
    )
    return cur.fetchone()


def a_acces_aux_boitiers(utilisateur: dict | None) -> bool:
    return bool(utilisateur and not utilisateur["archive"] and utilisateur["mobile_valide"])


def boitiers_autorises(cur, utilisateur: dict | None) -> list[dict]:
    """Boîtiers ouvrables par cet utilisateur (liste vide si aucun droit)."""
    if not a_acces_aux_boitiers(utilisateur):
        return []
    filtre, params = "", []
    if utilisateur["externe"]:
        cur.execute(
            "SELECT chantier_id FROM utilisateurs_chantiers WHERE utilisateur_id = %s",
            (utilisateur["id"],),
        )
        params = [r["chantier_id"] for r in cur.fetchall()]
        if not params:
            return []
        filtre = f" AND c.id IN ({','.join(['%s'] * len(params))})"
    cur.execute(
        f"""
        SELECT br.id, br.hostname, br.last_sync_at, c.id AS chantier_id, c.ref AS chantier_ref
        FROM boitier_registre br
        LEFT JOIN chantiers c ON c.id = br.chantier_id
        WHERE (c.archive = 0 OR c.id IS NULL){filtre}
        ORDER BY br.hostname
        """,
        params,
    )
    return cur.fetchall()
