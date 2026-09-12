from bottle import request, redirect, HTTPError
from web.ui import ui_app, BASE_PATH, view
from web.templating import get_current_user
from core.database import get_db

def is_admin(user):
    return user and user.get('is_admin', False)

@ui_app.get("/admin/utilisateurs")
def admin_users_list():
    current_user = get_current_user()
    if not is_admin(current_user):
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
    return view('admin_users', title="Gestion Utilisateurs", users=active_users, archived_users=archived_users)


@ui_app.post("/admin/utilisateurs")
def admin_users_create():
    current_user = get_current_user()
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
    
    data = request.forms
    ref = data.get('ref', '').strip()
    nom = data.get('nom', '').strip()
    emails = [e.strip() for e in data.get('emails', '').split(',') if e.strip()]
    cas = 1 if data.get('cas') else 0
    adm = 1 if data.get('adm') else 0
    wrk = 1 if data.get('wrk') else 0
    rot = 1 if data.get('rot') else 0
    
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO utilisateurs (ref, nom, cas, adm, wrk, rot)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (ref, nom, cas, adm, wrk, rot))
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
    current_user = get_current_user()
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
        
    data = request.forms
    ref = data.get('ref', '').strip()
    nom = data.get('nom', '').strip()
    emails = [e.strip() for e in data.get('emails', '').split(',') if e.strip()]
    cas = 1 if data.get('cas') else 0
    adm = 1 if data.get('adm') else 0
    wrk = 1 if data.get('wrk') else 0
    rot = 1 if data.get('rot') else 0
    
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE utilisateurs 
                SET ref=%s, nom=%s, cas=%s, adm=%s, wrk=%s, rot=%s
                WHERE id=%s
            """, (ref, nom, cas, adm, wrk, rot, user_id))
            
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
    current_user = get_current_user()
    if not is_admin(current_user):
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
    current_user = get_current_user()
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
        
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE utilisateurs SET archive = 0 WHERE id = %s", (user_id,))
        db.commit()
    finally:
        db.close()
        
    redirect(f"{BASE_PATH}/admin/utilisateurs")

@ui_app.get("/admin/chantiers-users")
def admin_chantiers_users():
    current_user = get_current_user()
    if not is_admin(current_user):
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
    current_user = get_current_user()
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
        
    uid = request.forms.get('uid')
    chantier_id = request.forms.get('chantier_id')
    new_uid = request.forms.get('new_uid')
    
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
