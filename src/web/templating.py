from __future__ import annotations

import bottle
from core.config import BASE_PATH
from core.database import get_db

class TemplateEngine:
    """
    Système de templates 'poupée russe' pour Reports (inspiré de rpinode).
    - render() : rend une petite poupée (un fragment HTML).
    - view() : rend la grande poupée (page complète avec layout) ou juste le
      cœur si la requête vient d'HTMX.
    """
    def __init__(self):
        self.base_path = BASE_PATH

    def get_current_user(self) -> dict:
        """
        Récupère l'utilisateur actuel par résolution d'email (OAuth2) 
        ou par UID simulé.
        """
        # On met en cache pour la durée de la requête
        if not hasattr(bottle.request, 'current_user'):
            user, real_user = self._resolve_user()
            
            # Ajout des propriétés calculées
            for u in (user, real_user):
                if u:
                    u['is_admin'] = bool(u.get('adm'))
                    u['is_ca'] = bool(u.get('cas'))
                    u['is_wait'] = not u['is_admin'] and not u['is_ca']
            
            bottle.request.current_user = user
            bottle.request.real_user = real_user

        return bottle.request.current_user

    def get_real_user(self) -> dict:
        """Récupère l'identité réelle (OAuth) de l'utilisateur."""
        self.get_current_user() # Assure le chargement
        return getattr(bottle.request, 'real_user', self.get_current_user())

    def _resolve_user(self) -> tuple[dict, dict]:
        """Logique interne de résolution. Retourne (current_user, real_user)."""
        # 1. On identifie d'abord l'utilisateur "réel" via l'Email OAuth2
        email = bottle.request.environ.get('X_EMAIL')
        user_name = bottle.request.environ.get('X_USER')
        real_user = None
        
        if email:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute("""
                        SELECT u.id, u.nom, u.cas, u.adm 
                        FROM utilisateurs u
                        JOIN utilisateurs_emails e ON u.id = e.utilisateur_id
                        WHERE e.email = %s
                    """, (email,))
                    row = cur.fetchone()
                    
                    if not row:
                        # Auto-enregistrement si inconnu
                        import hashlib
                        h = hashlib.md5(email.encode()).hexdigest()[:8]
                        ref_tmp = f"WAIT_{h}"
                        cur.execute("INSERT INTO utilisateurs (ref, nom, cas, adm) VALUES (%s, %s, 0, 0)", (ref_tmp, user_name or email))
                        new_id = cur.lastrowid
                        cur.execute("INSERT INTO utilisateurs_emails (utilisateur_id, email) VALUES (%s, %s)", (new_id, email))
                        db.commit()
                        real_user = {"id": new_id, "nom": user_name or email, "cas": 0, "adm": 0}
                    else:
                        real_user = dict(row)
            finally:
                db.close()
        
        # Si pas de mail, on prend Marc Fache (ID 1) comme identité réelle par défaut (dev local)
        if not real_user:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = 1")
                    real_user = dict(cur.fetchone())
            finally:
                db.close()

        # 2. Si on a un UID en paramètre ET que l'utilisateur réel est Admin, on simule un autre user
        user_id = bottle.request.query.get("uid")
        if user_id and real_user.get('adm'):
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute("SELECT id, nom, cas, adm FROM utilisateurs WHERE id = %s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        return dict(row), real_user
            finally:
                db.close()

        # 3. Par défaut, l'utilisateur actuel est l'utilisateur réel
        return real_user, real_user

    def _get_common_vars(self) -> dict:
        """Récupère l'utilisateur actuel et la liste globale pour le header."""
        current_user = self.get_current_user()
        real_user = self.get_real_user()
        
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT id, nom, cas, adm FROM utilisateurs ORDER BY nom")
                all_users = cur.fetchall()
                
                return {
                    "current_user": current_user,
                    "real_user": real_user,
                    "all_users": all_users,
                    "BASE_PATH": self.base_path,
                    "request_path": bottle.request.path
                }
        finally:
            db.close()

    def render(self, template_name: str, **kwargs) -> str:
        """Rend un fragment de template sans layout."""
        kwargs.setdefault('BASE_PATH', self.base_path)
        return bottle.template(template_name, **kwargs)

    def view(self, template_name: str, **kwargs) -> str:
        """
        Rend une page complète emboîtée dans le layout, sauf si HTMX demande
        un rafraîchissement partiel. Intercepte les utilisateurs en attente.
        """
        # 1. Préparation des variables communes (User, Path, Real Identity)
        common = self._get_common_vars()
        
        # On fusionne common dans kwargs en priorité pour la sécurité
        for k, v in common.items():
            kwargs[k] = v

        current_user = kwargs['current_user']

        # 2. Sécurité : Interceptions basées sur les rôles
        if current_user.get('is_wait') and template_name not in ('404', 'pending_validation'):
            # Utilisateur auto-enregistré mais non validé : accès restreint
            template_name = 'pending_validation'
            kwargs['title'] = 'Accès en attente'
        
        elif template_name in ('templates_maintenance', 'dev') and not current_user.get('is_admin'):
            # Pages réservées aux administrateurs
            template_name = '404'
            kwargs['title'] = 'Accès refusé'

        # 3. Rendu du cœur (la page demandée ou interceptée)
        content = self.render(template_name, **kwargs)

        # 3. Si HTMX, on renvoie juste le cœur (avec le titre pour l'onglet)
        if bottle.request.headers.get('HX-Request') == 'true':
            title = kwargs.get('title', 'Delta Thermic')
            return f"<title>{title}</title>\n{content}"

        # 4. Sinon, on emboîte dans la grande poupée (Layout)
        return self.render('layout', base=content, **kwargs)

# Instance unique exportée
engine = TemplateEngine()
render = engine.render
view = engine.view
get_current_user = engine.get_current_user
get_real_user = engine.get_real_user
