"""Tests de la gestion des utilisateurs mobiles (flags externe/mobile_valide
et invitation par email) ajoutee dans admin_users.py. Voir
docs/mobile/CAHIER_DES_CHARGES_APP_MOBILE.md (depot rpinode) pour le
contexte complet.
"""
from _helpers import call_wsgi


def _create_test_user(wsgi_app, base_path, ref, mobile_valide=True, email="test-mobile-invite@example.com"):
    body = f"ref={ref}&nom=Test+Mobile&emails={email}"
    if mobile_valide:
        body += "&mobile_valide=on"
    status, _, _ = call_wsgi(
        wsgi_app,
        f"{base_path}/admin/utilisateurs/edit",
        method="POST",
        body=body,
    )
    assert status in ["302 Found", "303 See Other", "200 OK"]


def _get_user_id(ref):
    from core.database import get_db
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM utilisateurs WHERE ref = %s", (ref,))
            row = cur.fetchone()
            return row["id"] if row else None
    finally:
        db.close()


def _cleanup_user(ref):
    from core.database import get_db
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM utilisateurs WHERE ref = %s", (ref,))
        db.commit()
    finally:
        db.close()


def test_admin_users_create_with_mobile_flags(wsgi_app, base_path):
    ref = "TEST_MOBILE_FLAGS"
    _cleanup_user(ref)
    try:
        _create_test_user(wsgi_app, base_path, ref, mobile_valide=True)

        status, _, body = call_wsgi(wsgi_app, f"{base_path}/admin/utilisateurs")
        assert status == "200 OK"
        assert ref in body
        # Le badge "M" (accès mobile) et le bouton d'envoi ne doivent
        # apparaître que pour un utilisateur avec mobile_valide=1.
        assert "mobile-invite" in body
    finally:
        _cleanup_user(ref)


def test_admin_users_mobile_invite_refuse_sans_flag(wsgi_app, base_path):
    ref = "TEST_MOBILE_NOFLAG"
    _cleanup_user(ref)
    try:
        _create_test_user(wsgi_app, base_path, ref, mobile_valide=False)
        user_id = _get_user_id(ref)
        assert user_id is not None

        status, headers, _ = call_wsgi(
            wsgi_app,
            f"{base_path}/admin/utilisateurs/{user_id}/mobile-invite",
            method="POST",
        )
        assert status in ["302 Found", "303 See Other"]
        assert "invite_error" in headers.get("Location", "")
    finally:
        _cleanup_user(ref)


def test_admin_users_mobile_invite_avec_flag_et_email(wsgi_app, base_path):
    ref = "TEST_MOBILE_INVITE"
    _cleanup_user(ref)
    try:
        _create_test_user(wsgi_app, base_path, ref, mobile_valide=True)
        user_id = _get_user_id(ref)
        assert user_id is not None

        status, headers, _ = call_wsgi(
            wsgi_app,
            f"{base_path}/admin/utilisateurs/{user_id}/mobile-invite",
            method="POST",
        )
        # Plus de tentative d'envoi SMTP (voir admin_users.py) : la cle est
        # toujours transmise via un jeton invite_copy_token (le corps complet
        # est garde cote serveur et jamais mis dans l'URL, pour eviter un 502
        # lie a une query string trop longue).
        assert status in ["302 Found", "303 See Other"]
        location = headers.get("Location", "")
        assert "invite_copy_token" in location

        from core.database import get_db
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM utilisateurs_activation_mobile WHERE utilisateur_id = %s",
                    (user_id,),
                )
                assert cur.fetchone()["n"] == 1
        finally:
            db.close()
    finally:
        _cleanup_user(ref)
