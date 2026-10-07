import datetime
import secrets
import threading
from urllib.parse import quote

from bottle import request, redirect, HTTPError
from web.ui import ui_app, BASE_PATH, view
from web.templating import get_current_user, get_real_user
from core.database import get_db
from services.fleet import hash_token
from services.email_sender import send_email, EmailConfigError, EmailSendError
from core.config import _ENV

def is_admin(user):
    return user and user.get('is_admin', False)

MOBILE_INVITE_EXPIRY = datetime.timedelta(hours=48)

# Repli quand l'envoi SMTP echoue (cf. investigation authentification
# Office 365, 2026-09-19) : le contenu de l'invitation est garde en
# memoire cote serveur (jamais dans l'URL de redirection, sinon la
# query string devient trop longue et provoque un 502 entre nginx et
# uwsgi) et recupere une seule fois via un jeton court passe en
# parametre. Un seul worker uwsgi tourne pour cette app (voir .ini,
# pas de "processes"), donc un simple dict en memoire protege par un
# verrou suffit.
_PENDING_INVITE_COPIES = {}
_PENDING_INVITE_LOCK = threading.Lock()
_PENDING_INVITE_TTL = datetime.timedelta(minutes=15)


def _build_mailto_url(dest, subject, body):
    """Lien mailto: pour ouvrir un brouillon pre-rempli dans le client mail
    par defaut (Outlook de preference ici), en repli quand l'envoi SMTP
    echoue (cf. investigation authentification Office 365, 2026-09-19).
    RFC 6068 : CRLF pour les sauts de ligne du corps."""
    return (
        f"mailto:{quote(dest, safe='@')}"
        f"?subject={quote(subject, safe='')}"
        f"&body={quote(body.replace(chr(10), chr(13) + chr(10)), safe='')}"
    )


def _store_pending_invite_copy(dest, subject, body):
    token = secrets.token_urlsafe(16)
    now = datetime.datetime.now()
    with _PENDING_INVITE_LOCK:
        # Purge des entrees expirees au passage.
        for key in [k for k, v in _PENDING_INVITE_COPIES.items() if now - v["created_at"] > _PENDING_INVITE_TTL]:
            del _PENDING_INVITE_COPIES[key]
        _PENDING_INVITE_COPIES[token] = {
            "dest": dest,
            "body": body,
            "mailto_url": _build_mailto_url(dest, subject, body),
            "created_at": now,
        }
    return token


def _pop_pending_invite_copy(token):
    if not token:
        return None
    with _PENDING_INVITE_LOCK:
        entry = _PENDING_INVITE_COPIES.pop(token, None)
    if not entry or datetime.datetime.now() - entry["created_at"] > _PENDING_INVITE_TTL:
        return None
    return entry

@ui_app.get("/admin/utilisateurs")
def admin_users_list():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    users = []
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT u.*, GROUP_CONCAT(e.email SEPARATOR ', ') as emails, u.archive
                FROM utilisateurs u
                LEFT JOIN utilisateurs_emails e ON e.utilisateur_id = u.id
                GROUP BY u.id
                ORDER BY u.nom ASC
            """)
            users = cur.fetchall()
    finally:
        db.close()


    active_users = [u for u in users if not u.get('archive')]
    archived_users = [u for u in users if u.get('archive')]
    invite_status = request.query.get('invite')
    invite_error = request.query.get('invite_error')
    invite_copy_dest = None
    invite_copy_body = None
    invite_mailto_url = None
    pending = _pop_pending_invite_copy(request.query.get('invite_copy_token'))
    if pending:
        invite_copy_dest = pending["dest"]
        invite_copy_body = pending["body"]
        invite_mailto_url = pending["mailto_url"]
    return view(
        'admin_users', title="Gestion Utilisateurs", users=active_users,
        archived_users=archived_users, invite_status=invite_status,
        invite_error=invite_error, invite_copy_dest=invite_copy_dest,
        invite_copy_body=invite_copy_body, invite_mailto_url=invite_mailto_url,
    )


@ui_app.post("/admin/utilisateurs/edit")
def admin_users_edit():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    data = request.forms.decode('utf-8')
    ref = data.get('ref', '').strip()
    nom = data.get('nom', '').strip()
    emails = [e.strip() for e in data.get('emails', '').split(',') if e.strip()]
    cas = 1 if data.get('cas') else 0
    adm = 1 if data.get('adm') else 0
    wrk = 1 if data.get('wrk') else 0
    rot = 1 if data.get('rot') else 0
    externe = 1 if data.get('externe') else 0
    mobile_valide = 1 if data.get('mobile_valide') else 0

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO utilisateurs (ref, nom, cas, adm, wrk, rot, externe, mobile_valide)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (ref, nom, cas, adm, wrk, rot, externe, mobile_valide))
            user_id = cur.lastrowid

            for email in emails:
                cur.execute("""
                    INSERT INTO utilisateurs_emails (utilisateur_id, email)
                    VALUES (%s, %s)
                """, (user_id, email))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/utilisateurs")

@ui_app.post("/admin/utilisateurs/<user_id:int>/update")
def admin_users_update(user_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    data = request.forms.decode('utf-8')
    ref = data.get('ref', '').strip()
    nom = data.get('nom', '').strip()
    emails = [e.strip() for e in data.get('emails', '').split(',') if e.strip()]
    cas = 1 if data.get('cas') else 0
    adm = 1 if data.get('adm') else 0
    wrk = 1 if data.get('wrk') else 0
    rot = 1 if data.get('rot') else 0
    externe = 1 if data.get('externe') else 0
    mobile_valide = 1 if data.get('mobile_valide') else 0

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE utilisateurs
                SET ref=%s, nom=%s, cas=%s, adm=%s, wrk=%s, rot=%s, externe=%s, mobile_valide=%s
                WHERE id=%s
            """, (ref, nom, cas, adm, wrk, rot, externe, mobile_valide, user_id))

            cur.execute("DELETE FROM utilisateurs_emails WHERE utilisateur_id=%s", (user_id,))
            for email in emails:
                cur.execute("""
                    INSERT INTO utilisateurs_emails (utilisateur_id, email)
                    VALUES (%s, %s)
                """, (user_id, email))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/utilisateurs")

@ui_app.post("/admin/utilisateurs/<user_id:int>/archive")
def admin_users_archive(user_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE utilisateurs SET archive = 1 WHERE id = %s", (user_id,))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/utilisateurs")


@ui_app.post("/admin/utilisateurs/<user_id:int>/unarchive")
def admin_users_unarchive(user_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE utilisateurs SET archive = 0 WHERE id = %s", (user_id,))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/utilisateurs")


@ui_app.post("/admin/utilisateurs/<user_id:int>/mobile-invite")
def admin_users_mobile_invite(user_id):
    """
    Genere une cle d'activation a usage unique pour l'application mobile
    et envoie un email d'invitation a l'utilisateur (premier email
    connu). Necessite que la case "Acces mobile" soit cochee pour cet
    utilisateur (voir docs/mobile/CAHIER_DES_CHARGES_APP_MOBILE.md,
    section 4.3, dans le depot rpinode).
    """
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, ref, nom, archive, mobile_valide FROM utilisateurs WHERE id = %s",
                (user_id,),
            )
            user = cur.fetchone()
            if not user or user["archive"]:
                redirect(f"{BASE_PATH}/admin/utilisateurs?invite_error=Utilisateur+introuvable+ou+archive")
                return
            if not user["mobile_valide"]:
                redirect(f"{BASE_PATH}/admin/utilisateurs?invite_error=Cochez+d%27abord+Acces+mobile+pour+cet+utilisateur")
                return

            cur.execute(
                "SELECT email FROM utilisateurs_emails WHERE utilisateur_id = %s LIMIT 1",
                (user_id,),
            )
            email_row = cur.fetchone()
            if not email_row:
                redirect(f"{BASE_PATH}/admin/utilisateurs?invite_error=Aucun+email+enregistre+pour+cet+utilisateur")
                return
            destinataire = email_row["email"]

            cle = secrets.token_urlsafe(16)
            expire_at = datetime.datetime.now() + MOBILE_INVITE_EXPIRY
            cur.execute(
                "INSERT INTO utilisateurs_activation_mobile (utilisateur_id, cle_hash, expire_at) "
                "VALUES (%s, %s, %s)",
                (user_id, hash_token(cle), expire_at),
            )
        db.commit()
    finally:
        db.close()

    play_store_url = _ENV.get("MOBILE_APP_PLAY_STORE_URL", "").strip()
    lien_ligne = (
        f"1. Installez l'application depuis ce lien : {play_store_url}\n"
        if play_store_url
        else "1. Installez l'application (lien a venir, contactez votre administrateur si besoin).\n"
    )
    corps = (
        f"Bonjour {user['nom'] or user['ref']},\n\n"
        "Un accès à l'application mobile rpinode vous a été créé.\n\n"
        f"{lien_ligne}"
        "2. Ouvrez l'application et connectez-vous avec Google si demandé.\n"
        f"3. Saisissez cette clé d'activation lors du premier lancement :\n\n"
        f"   {cle}\n\n"
        f"Cette clé est valable 48 heures et à usage unique.\n\n"
        "Note : lors de l'installation, votre téléphone peut afficher un "
        "avertissement si l'application ne provient pas encore du Play "
        "Store public — c'est normal pour cette phase de test, suivez "
        "simplement les instructions à l'écran.\n\n"
        "-- Deltathermic"
    )

    subject = "Accès à l'application mobile rpinode"
    try:
        send_email(destinataire, subject, corps)
    except (EmailConfigError, EmailSendError) as exc:
        # Repli en attendant que l'envoi SMTP fonctionne (cf. investigation
        # authentification Office 365, 2026-09-19) : la cle est deja creee
        # et valide, on permet a l'admin d'ouvrir un brouillon pre-rempli
        # dans son client mail (mailto:, typiquement Outlook) ou de
        # copier/coller le contenu pour le transmettre manuellement.
        # Le contenu est garde cote serveur (voir _store_pending_invite_copy)
        # et pas dans l'URL, qui deviendrait trop longue et causerait un
        # 502 (limite de taille d'en-tete entre nginx et uwsgi).
        token = _store_pending_invite_copy(destinataire, subject, corps)
        params = (
            "invite_error=" + quote(f"Cle creee mais envoi email echoue : {str(exc)[:150]}")
            + "&invite_copy_token=" + token
        )
        redirect(f"{BASE_PATH}/admin/utilisateurs?{params}")
        return

    redirect(f"{BASE_PATH}/admin/utilisateurs?invite=ok")


@ui_app.get("/admin/chantiers-users")
def admin_chantiers_users():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    uid = request.query.get('uid')
    db = get_db()
    users = []
    tous_chantiers = []
    chantiers_utilisateur = []

    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, ref, nom FROM utilisateurs WHERE archive = 0 ORDER BY nom ASC")
            users = cur.fetchall()

            # Chaque chantier a un seul chargé d'affaires (chantiers.utilisateurs_id).
            # La table `filtres` sert uniquement à catégoriser les remarques et n'a
            # aucun rapport avec l'attribution des chantiers.
            cur.execute("""
                SELECT c.id, c.ref, c.adresse, c.utilisateurs_id, u.nom as charge_affaires
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                WHERE c.archive = 0
                ORDER BY c.ref ASC
            """)
            tous_chantiers = cur.fetchall()

            if uid and uid.isdigit():
                cur.execute("""
                    SELECT id, ref, adresse
                    FROM chantiers
                    WHERE utilisateurs_id = %s AND archive = 0
                    ORDER BY ref ASC
                """, (int(uid),))
                chantiers_utilisateur = cur.fetchall()
    finally:
        db.close()

    return view('admin_chantiers_users', title="Affectation Chantiers", users=users, chantiers=tous_chantiers, chantiers_utilisateur=chantiers_utilisateur, selected_uid=uid)

@ui_app.post("/admin/chantiers-users/assign")
def admin_chantiers_users_assign():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    data = request.forms.decode('utf-8')
    uid = data.get('uid')
    chantier_id = data.get('chantier_id')
    new_uid = data.get('new_uid')

    if not chantier_id or not new_uid:
        redirect(f"{BASE_PATH}/admin/chantiers-users?uid={uid or ''}")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE chantiers SET utilisateurs_id = %s WHERE id = %s", (new_uid, chantier_id))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/chantiers-users?uid={uid or ''}")


@ui_app.get("/admin/chantiers")
def admin_chantiers_list():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    chantiers = []
    users = []
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.*, u.nom as charge_affaires
                FROM chantiers c
                LEFT JOIN utilisateurs u ON c.utilisateurs_id = u.id
                ORDER BY c.ref ASC
            """)
            chantiers = cur.fetchall()

            cur.execute("SELECT id, ref, nom FROM utilisateurs WHERE archive = 0 ORDER BY nom ASC")
            users = cur.fetchall()
    finally:
        db.close()

    active_chantiers = [c for c in chantiers if not c.get('archive')]
    archived_chantiers = [c for c in chantiers if c.get('archive')]
    return view('admin_chantiers', title="Gestion Chantiers", chantiers=active_chantiers, archived_chantiers=archived_chantiers, users=users)


@ui_app.post("/admin/chantiers/create")
def admin_chantiers_create():
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    data = request.forms.decode('utf-8')
    ref = data.get('ref', '').strip()
    adresse = data.get('adresse', '').strip() or None
    geolocalisation = data.get('geolocalisation', '').strip() or None
    utilisateurs_id = data.get('utilisateurs_id')
    if not utilisateurs_id or not str(utilisateurs_id).isdigit():
        utilisateurs_id = real_user.get('id', 1)
    else:
        utilisateurs_id = int(utilisateurs_id)

    if not ref:
        redirect(f"{BASE_PATH}/admin/chantiers")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO chantiers (ref, adresse, geolocalisation, utilisateurs_id)
                VALUES (%s, %s, %s, %s)
            """, (ref, adresse, geolocalisation, utilisateurs_id))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/chantiers")


@ui_app.post("/admin/chantiers/<chantier_id:int>/update")
def admin_chantiers_update(chantier_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    data = request.forms.decode('utf-8')
    ref = data.get('ref', '').strip()
    adresse = data.get('adresse', '').strip() or None
    geolocalisation = data.get('geolocalisation', '').strip() or None
    utilisateurs_id = data.get('utilisateurs_id')
    if not utilisateurs_id or not str(utilisateurs_id).isdigit():
        utilisateurs_id = real_user.get('id', 1)
    else:
        utilisateurs_id = int(utilisateurs_id)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE chantiers
                SET ref=%s, adresse=%s, geolocalisation=%s, utilisateurs_id=%s
                WHERE id=%s
            """, (ref, adresse, geolocalisation, utilisateurs_id, chantier_id))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/chantiers")


@ui_app.post("/admin/chantiers/<chantier_id:int>/archive")
def admin_chantiers_archive(chantier_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE chantiers SET archive = 1 WHERE id = %s", (chantier_id,))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/chantiers")


@ui_app.post("/admin/chantiers/<chantier_id:int>/unarchive")
def admin_chantiers_unarchive(chantier_id):
    real_user = get_real_user()
    if not is_admin(real_user):
        raise HTTPError(403, "Accès refusé.")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE chantiers SET archive = 0 WHERE id = %s", (chantier_id,))
        db.commit()
    finally:
        db.close()

    redirect(f"{BASE_PATH}/admin/chantiers")
