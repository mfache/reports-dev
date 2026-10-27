"""Raccourcis de chantier (services/raccourcis.py) : liste envoyée par le
boîtier dans /sync, affichée sur la page « Boîtiers »."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from services import raccourcis


class CurseurFactice:
    """Enregistre les requêtes ; SELECT id FROM chantiers répond d'après `chantiers`."""

    def __init__(self, chantiers=(), lignes=()):
        self.chantiers = set(chantiers)
        self.lignes = list(lignes)
        self.requetes = []
        self._un = None

    def execute(self, sql, params=()):
        self.requetes.append((" ".join(sql.split()), params))
        if sql.startswith("SELECT id FROM chantiers"):
            self._un = {"id": params[0]} if params[0] in self.chantiers else None

    def fetchone(self):
        return self._un

    def fetchall(self):
        return self.lignes

    def inserts(self):
        return [p for s, p in self.requetes if s.startswith("INSERT INTO chantier_raccourcis")]


@pytest.fixture(autouse=True)
def _sans_schema():
    with patch("services.raccourcis.assurer_schema"):
        yield


@pytest.mark.parametrize("url,attendu", [
    ("https://10.103.40.7/UI/", True),
    ("http://192.168.1.20:8080/", True),
    ("ftp://10.103.40.7/", False),
    ("https://gtc.local/", False),
    ("https://8.8.8.8/", False),
    ("http://127.0.0.1/", False),
    ("https://10.103.40.7:99999/", False),
])
def test_url_valide(url, attendu):
    assert raccourcis.url_valide(url) is attendu


def test_push_remplace_la_liste_du_boitier_sur_le_chantier_designe():
    cur = CurseurFactice(chantiers={23})
    raccourcis.push_raccourcis(cur, 2, 28, "rpi01", {"external_id": "23", "items": [
        {"label": "GTC Johnson Controls", "url": "https://10.103.40.7/UI/"},
        {"label": "Pirate", "url": "https://8.8.8.8/"},
        {"label": "", "url": "https://10.103.40.8/"},
    ]})
    supprime = [p for s, p in cur.requetes if s.startswith("DELETE FROM chantier_raccourcis")]
    assert supprime == [(23, "rpi01")]
    assert cur.inserts() == [(23, "GTC Johnson Controls", "https://10.103.40.7/UI/", "rpi01")]


def test_push_chantier_inconnu_retombe_sur_le_chantier_resolu():
    cur = CurseurFactice(chantiers=set())
    raccourcis.push_raccourcis(cur, 2, 28, "rpi01", {"external_id": "999", "items": [
        {"label": "GTC", "url": "https://10.103.40.7/"}]})
    assert cur.inserts() == [(28, "GTC", "https://10.103.40.7/", "rpi01")]


def test_push_liste_vide_efface():
    cur = CurseurFactice(chantiers={23})
    raccourcis.push_raccourcis(cur, 2, None, "rpi01", {"external_id": 23, "items": []})
    assert any(s.startswith("DELETE") for s, _ in cur.requetes)
    assert cur.inserts() == []


def test_push_sans_chantier_ne_fait_rien():
    cur = CurseurFactice()
    raccourcis.push_raccourcis(cur, 2, None, "rpi01", {"external_id": None, "items": [
        {"label": "GTC", "url": "https://10.103.40.7/"}]})
    assert not any(s.startswith(("DELETE", "INSERT")) for s, _ in cur.requetes)


def test_raccourcis_par_chantier():
    cur = CurseurFactice(lignes=[{"chantier_id": 23, "libelle": "GTC", "url": "https://10.103.40.7/"}])
    assert raccourcis.raccourcis_par_chantier(cur, [23, None]) == {
        23: [{"libelle": "GTC", "url": "https://10.103.40.7/"}]}
    assert raccourcis.raccourcis_par_chantier(CurseurFactice(), []) == {}
