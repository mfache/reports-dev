"""Authentification et donnees pour l'application mobile native rpinode :
activation de compte par cle a usage unique, gestion des sessions
applicatives, liste des boitiers visibles et emission des jetons d'acces
courte duree par boitier (relayes ensuite aux boitiers via /sync, voir
services/sync.py). Voir docs/mobile/CAHIER_DES_CHARGES_APP_MOBILE.md dans
le depot rpinode pour le contexte complet.

Sur le modele des autres modules services/* : ce fichier fait
`from web.api import api_app` puis enregistre ses routes par effet de
bord de l'import (voir web/api.py).
"""
from __future__ import annotations

import datetime
import secrets

from bottle import request

from core.database import get_db
from services.fleet import hash_token
from web.api import api_app
from web.responses import json_error, json_ok

ACCESS_TOKEN_LIFETIME = datetime.timedelta(hours=2)
# Seuil "en ligne" provisoire (point ouvert du cahier des charges mobile,
# voir docs/mobile/CAHIER_DES_CHARGES_APP_MOBILE.md section 15).
ONLINE_THRESHOLD_MINUTES = 5


def authenticate_mobile_user(cur):
    """Authentifie une requete de l'app mobile via Authorization: Bearer <session_token>.

    Retourne un dict (session_id, utilisateur_id, ref, nom, externe) ou None.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    if not token:
        return None
    token_hash = hash_token(token)
    cur.execute(
        """
        SELECT s.id AS session_id, u.id AS utilisateur_id, u.ref, u.nom, u.externe
        FROM utilisateurs_sessions_mobile s
        JOIN utilisateurs u ON u.id = s.utilisateur_id
        WHERE s.token_hash = %s AND s.revoque = 0
          AND u.archive = 0 AND u.mobile_valide = 1
        """,
        (token_hash,),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE utilisateurs_sessions_mobile SET derniere_utilisation = NOW() WHERE id = %s",
            (row["session_id"],),
        )
    return row


@api_app.post("/mobile/activate")
def mobile_activate():
    """
    Echange la cle d'activation a usage unique (envoyee par email par un
    admin) contre un jeton de session applicatif pour l'app mobile.

    Payload:
        {"cle": "<cle recue par email>"}

    Reponse:
        {
            "ok": true,
            "session_token": "<jeton opaque, a conserver sur l'appareil>",
            "utilisateur": {"ref": "TOM", "nom": "Tomy Dupont", "externe": false}
        }
    """
    data = request.json or {}
    cle = (data.get("cle") or "").strip()
    if not cle:
        return json_error(400, "Cle d'activation requise.")

    cle_hash = hash_token(cle)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM utilisateurs_activation_mobile WHERE cle_hash = %s",
                (cle_hash,),
            )
            activation = cur.fetchone()
            if not activation:
                return json_error(401, "Cle d'activation invalide.")
            if activation["utilisee_at"] is not None:
                return json_error(410, "Cette cle d'activation a deja ete utilisee.")
            if activation["expire_at"] < datetime.datetime.now():
                return json_error(410, "Cette cle d'activation a expire.")

            cur.execute(
                "SELECT id, ref, nom, externe, archive, mobile_valide FROM utilisateurs WHERE id = %s",
                (activation["utilisateur_id"],),
            )
            utilisateur = cur.fetchone()
            if not utilisateur or utilisateur["archive"]:
                return json_error(403, "Compte utilisateur desactive.")
            if not utilisateur["mobile_valide"]:
                return json_error(403, "Compte non valide pour l'application mobile.")

            cur.execute(
                "UPDATE utilisateurs_activation_mobile SET utilisee_at = NOW() WHERE id = %s",
                (activation["id"],),
            )

            session_token = secrets.token_urlsafe(32)
            cur.execute(
                "INSERT INTO utilisateurs_sessions_mobile (utilisateur_id, token_hash) VALUES (%s, %s)",
                (utilisateur["id"], hash_token(session_token)),
            )

        return json_ok({
            "session_token": session_token,
            "utilisateur": {
                "ref": utilisateur["ref"],
                "nom": utilisateur["nom"],
                "externe": bool(utilisateur["externe"]),
            },
        })
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()


@api_app.get("/mobile/boitiers")
def mobile_list_boitiers():
    """
    Liste les boitiers de la flotte visibles par l'utilisateur mobile
    authentifie (restreint aux chantiers autorises pour un compte externe).

    Headers:
        Authorization: Bearer <session_token>

    Reponse:
        {
            "ok": true,
            "boitiers": [
                {
                    "hostname": "rpi01",
                    "chantier": {"id": 12, "ref": "Hopital Sud"},
                    "last_sync_at": "2026-09-19T11:29:40",
                    "en_ligne": true,
                    "ip_tailscale": "100.64.0.11"
                }
            ]
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            auth = authenticate_mobile_user(cur)
            if not auth:
                return json_error(401, "Session invalide ou expiree.")

            params = []
            chantier_filter_sql = ""
            if auth["externe"]:
                cur.execute(
                    "SELECT chantier_id FROM utilisateurs_chantiers WHERE utilisateur_id = %s",
                    (auth["utilisateur_id"],),
                )
                chantier_ids = [r["chantier_id"] for r in cur.fetchall()]
                if not chantier_ids:
                    return json_ok({"boitiers": []})
                placeholders = ",".join(["%s"] * len(chantier_ids))
                chantier_filter_sql = f" AND c.id IN ({placeholders})"
                params = chantier_ids

            cur.execute(
                f"""
                SELECT br.hostname, br.last_sync_at, br.last_ip,
                       c.id AS chantier_id, c.ref AS chantier_ref
                FROM boitier_registre br
                LEFT JOIN chantiers c ON c.id = br.chantier_id
                WHERE (c.archive = 0 OR c.id IS NULL){chantier_filter_sql}
                ORDER BY br.hostname ASC
                """,
                params,
            )
            rows = cur.fetchall()

        now = datetime.datetime.now()
        boitiers = []
        for r in rows:
            en_ligne = bool(
                r["last_sync_at"]
                and (now - r["last_sync_at"]) <= datetime.timedelta(minutes=ONLINE_THRESHOLD_MINUTES)
            )
            boitiers.append({
                "hostname": r["hostname"],
                "chantier": {"id": r["chantier_id"], "ref": r["chantier_ref"]} if r["chantier_id"] else None,
                "last_sync_at": r["last_sync_at"],
                "en_ligne": en_ligne,
                "ip_tailscale": r["last_ip"],
            })

        return json_ok({"boitiers": boitiers})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()


@api_app.post("/mobile/boitiers/<hostname>/access-token")
def mobile_boitier_access_token(hostname):
    """
    Genere un jeton d'acces courte duree pour ouvrir la WebView d'un
    boitier precis depuis l'app mobile. Ce jeton est ensuite recupere par
    le boitier via l'extension du payload /sync (voir services/sync.py).

    Headers:
        Authorization: Bearer <session_token>

    Reponse:
        {"ok": true, "access_token": "<opaque>", "expire_at": "2026-09-19T13:29:40"}
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            auth = authenticate_mobile_user(cur)
            if not auth:
                return json_error(401, "Session invalide ou expiree.")

            cur.execute(
                """
                SELECT br.id AS boitier_id, br.chantier_id, c.archive AS chantier_archive
                FROM boitier_registre br
                LEFT JOIN chantiers c ON c.id = br.chantier_id
                WHERE br.hostname = %s
                """,
                (hostname,),
            )
            boitier = cur.fetchone()
            if not boitier:
                return json_error(404, "Boitier introuvable.")

            if auth["externe"]:
                cur.execute(
                    "SELECT 1 FROM utilisateurs_chantiers WHERE utilisateur_id = %s AND chantier_id = %s",
                    (auth["utilisateur_id"], boitier["chantier_id"]),
                )
                if not cur.fetchone():
                    return json_error(403, "Acces refuse a ce boitier.")

            # Purge opportuniste des jetons expires (evite la croissance
            # illimitee de la table, pas besoin d'un cron dedie).
            cur.execute("DELETE FROM utilisateurs_acces_boitier WHERE expire_at < NOW()")

            access_token = secrets.token_urlsafe(32)
            expire_at = datetime.datetime.now() + ACCESS_TOKEN_LIFETIME
            cur.execute(
                "INSERT INTO utilisateurs_acces_boitier "
                "(utilisateur_id, boitier_id, token_hash, expire_at) VALUES (%s, %s, %s, %s)",
                (auth["utilisateur_id"], boitier["boitier_id"], hash_token(access_token), expire_at),
            )

        return json_ok({"access_token": access_token, "expire_at": expire_at})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()


@api_app.post("/mobile/logout")
def mobile_logout():
    """
    Revoque la session applicative mobile courante.

    Headers:
        Authorization: Bearer <session_token>

    Reponse:
        {"ok": true}
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            auth = authenticate_mobile_user(cur)
            if not auth:
                return json_error(401, "Session invalide ou expiree.")
            cur.execute(
                "UPDATE utilisateurs_sessions_mobile SET revoque = 1 WHERE id = %s",
                (auth["session_id"],),
            )
        return json_ok({})
    finally:
        db.close()
