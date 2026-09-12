from bottle import request, redirect, HTTPError
from web.ui import ui_app, BASE_PATH, view
from core.database import get_db

def is_admin(user):
    return user and user.get('is_admin', False)

@ui_app.get("/admin/utilisateurs")
def admin_users_list():
    current_user = request.environ.get('reports.user', {})
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
    
    db = get_db()
    users = []
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT u.*, GROUP_CONCAT(e.email SEPARATOR ', ') as emails
                FROM utilisateurs u
                LEFT JOIN utilisateurs_emails e ON e.utilisateur_id = u.id
                GROUP BY u.id
                ORDER BY u.nom ASC
            """)
            users = cur.fetchall()
    finally:
        db.close()
        
    return view('admin_users', title="Gestion Utilisateurs", users=users)

@ui_app.post("/admin/utilisateurs")
def admin_users_create():
    current_user = request.environ.get('reports.user', {})
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
    current_user = request.environ.get('reports.user', {})
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

@ui_app.post("/admin/utilisateurs/<user_id:int>/delete")
def admin_users_delete(user_id):
    current_user = request.environ.get('reports.user', {})
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
        
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM utilisateurs_emails WHERE utilisateur_id=%s", (user_id,))
            cur.execute("DELETE FROM utilisateurs WHERE id=%s", (user_id,))
        db.commit()
    finally:
        db.close()
        
    redirect(f"{BASE_PATH}/admin/utilisateurs")

@ui_app.get("/admin/chantiers-users")
def admin_chantiers_users():
    current_user = request.environ.get('reports.user', {})
    if not is_admin(current_user):
        raise HTTPError(403, "Accès refusé.")
        
    return view('admin_chantiers_users', title="Affectation Chantiers")
