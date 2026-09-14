from _helpers import call_wsgi


def test_admin_chantiers_page_access(wsgi_app, base_path):
    # Tests that /admin/chantiers endpoint responds 200 OK for admin user
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/admin/chantiers")
    assert status == "200 OK"
    assert "Gestion des Chantiers" in body


def test_admin_chantiers_crud_flow(wsgi_app, base_path):
    # 1. Create a test chantier
    status, _, _ = call_wsgi(
        wsgi_app,
        f"{base_path}/admin/chantiers/create",
        method="POST",
        body="ref=TEST_CHANTIER_TEST&adresse=123+Test+Street&geolocalisation=50.1,4.2"
    )
    assert status in ["302 Found", "303 See Other", "200 OK"]

    # 2. Check it appears on /admin/chantiers
    status, _, body = call_wsgi(wsgi_app, f"{base_path}/admin/chantiers")
    assert status == "200 OK"
    assert "TEST_CHANTIER_TEST" in body


def test_admin_chantiers_crud_flow_with_accents(wsgi_app, base_path):
    # Tests creating a chantier with accented characters in ref and address
    status, _, _ = call_wsgi(
        wsgi_app,
        f"{base_path}/admin/chantiers/create",
        method="POST",
        body="ref=TEST_ÉLÉPHANT&adresse=Grand'Rue,+Châtelet&geolocalisation=50.1,4.2"
    )
    assert status in ["302 Found", "303 See Other", "200 OK"]

    status, _, body = call_wsgi(wsgi_app, f"{base_path}/admin/chantiers")
    assert status == "200 OK"
    assert "TEST_ÉLÉPHANT" in body
    assert "Châtelet" in body
