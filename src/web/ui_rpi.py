"""Page « Boîtiers » (choix d'un boîtier à ouvrir) et point de contrôle
nginx du proxy ``/rpi/<hostname>/``. Logique d'accès : services/acces_boitiers.py.
"""
from __future__ import annotations

import datetime
import os

from bottle import request, response

from core.config import BASE_PATH
from core.database import get_db
from services.acces_boitiers import (HOSTNAME_VALIDE, a_acces_aux_boitiers,
                                     boitiers_autorises, email_session_oauth2,
                                     ips_tailscale, utilisateur_par_email)
from services.raccourcis import raccourcis_par_chantier
from web.templating import engine, view
from web.ui import ui_app

#: Préfixe public du proxy. Production : /rpi ; l'instance de dev
#: (/reports-dev) a le sien pour ne jamais partager de route avec la prod.
RPI_PROXY_PATH = os.environ.get("REPORTS_RPI_PROXY_PATH") or (
    "/rpi-dev" if BASE_PATH == "/reports-dev" else "/rpi")

#: Seuil « en ligne », identique à celui de services/mobile.py.
EN_LIGNE = datetime.timedelta(minutes=5)


@ui_app.get("/rpi")
def rpi_boitiers():
    utilisateur = engine.get_current_user()
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, ref, nom, externe, mobile_valide, archive FROM utilisateurs WHERE id = %s",
                (utilisateur["id"],),
            )
            fiche = cur.fetchone()
            boitiers = boitiers_autorises(cur, fiche)
            raccourcis = raccourcis_par_chantier(cur, [b["chantier_id"] for b in boitiers])
    finally:
        db.close()

    ips = ips_tailscale()
    maintenant = datetime.datetime.now()
    for b in boitiers:
        b["en_ligne"] = bool(b["last_sync_at"] and maintenant - b["last_sync_at"] <= EN_LIGNE)
        b["joignable"] = b["hostname"] in ips
        b["url"] = f"{RPI_PROXY_PATH}/{b['hostname']}/"
        b["raccourcis"] = raccourcis.get(b["chantier_id"], [])

    return view("rpi_boitiers", title="Boîtiers - Deltathermic", boitiers=boitiers,
                autorise=a_acces_aux_boitiers(fiche),
                refus=request.query.get("refus", ""))


@ui_app.get("/rpi/authz")
def rpi_authz():
    """Sous-requête ``auth_request`` de nginx, pour chaque requête vers
    ``/rpi/<hostname>/...``. 200 + ``X-Rpi-Upstream`` si l'accès est permis,
    401 sans session Azure (nginx renvoie vers la connexion), 403 sinon.
    L'identité vient toujours de la vraie session (jamais de ?uid=)."""
    hostname = request.environ.get("X_RPI_HOST", "")
    if not HOSTNAME_VALIDE.fullmatch(hostname):
        response.status = 403
        return ""

    email = email_session_oauth2(request.environ.get("HTTP_COOKIE"))
    if not email:
        response.status = 401
        return ""

    db = get_db()
    try:
        with db.cursor() as cur:
            utilisateur = utilisateur_par_email(cur, email)
            autorises = {b["hostname"] for b in boitiers_autorises(cur, utilisateur)}
    finally:
        db.close()

    ip = ips_tailscale().get(hostname)
    if hostname not in autorises or not ip:
        response.status = 403
        return ""

    response.set_header("X-Rpi-Upstream", ip)
    response.set_header("X-Rpi-User", email)
    return ""
