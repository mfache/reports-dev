"""_resolve_or_create_chantier sans antenne GSM : le chantier annoncé par le
boîtier (site_hint_name) est retenu s'il existe et n'est pas provisoire."""
from __future__ import annotations

from services.chantiers import _resolve_or_create_chantier


class CurseurFactice:
    """Répond à _fetch_chantier_by_ref à partir d'un dictionnaire ref -> ligne."""

    def __init__(self, chantiers):
        self.chantiers = chantiers
        self.requetes = []
        self._resultat = None

    def execute(self, sql, params=()):
        self.requetes.append(sql)
        self._resultat = self.chantiers.get(params[0]) if "WHERE ref=" in sql else None

    def fetchone(self):
        return self._resultat


def test_sans_antenne_retient_le_chantier_annonce():
    cur = CurseurFactice({"CCSE": {"id": 23, "ref": "CCSE"}})
    assert _resolve_or_create_chantier(cur, 2, 28, {}, "CCSE") == {"id": 23, "ref": "CCSE"}
    assert all("INSERT" not in sql for sql in cur.requetes)


def test_sans_antenne_chantier_inconnu_ne_change_rien():
    cur = CurseurFactice({})
    assert _resolve_or_create_chantier(cur, 2, 28, None, "INCONNU") is None


def test_sans_antenne_indice_provisoire_ignore():
    cur = CurseurFactice({"TEMP-206-01-1": {"id": 30, "ref": "TEMP-206-01-1"}})
    assert _resolve_or_create_chantier(cur, 2, 28, {}, "TEMP-206-01-1") is None
    assert cur.requetes == []


def test_sans_antenne_sans_indice():
    cur = CurseurFactice({})
    assert _resolve_or_create_chantier(cur, 2, 28, {}, None) is None
