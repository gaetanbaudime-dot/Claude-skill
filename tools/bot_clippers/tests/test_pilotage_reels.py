"""20/10 : onglet « Pilotage reels » (Cockpit Clipping : cards Reels 15 j et Vues 15 j)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard  # noqa: E402


def _serie(*reels):
    return {"reels": {str(i): r for i, r in enumerate(reels)}}


def test_jour_de_paris_et_derniere_vue():
    s = _serie(
        {"publie": "2026-10-19T22:30:00+00:00", "vues": [["2026-10-20T06:00:00+00:00", 100], ["2026-10-20T12:00:00+00:00", 900]]},
        {"publie": "2026-10-19T10:00:00+00:00", "vues": []},
    )
    lignes = dashboard.lignes_reels([("Sarah", "Yves", s)], date(2026, 10, 20))
    # 22 h 30 UTC le 19 = 0 h 30 à Paris le 20 : compté le 20, avec sa dernière valeur (900)
    assert lignes == [["2026-10-19", "Sarah", "Yves", "1", "0", "0"], ["2026-10-20", "Sarah", "Yves", "1", "900", "1"]]


def test_fenetre_de_15_jours_et_comptes_sans_serie():
    s = _serie({"publie": "2026-10-05T12:00:00+00:00"}, {"publie": "2026-10-06T12:00:00+00:00", "vues": [["2026-10-08T12:00:00+00:00", 5]]},
               {"publie": "pas une date"}, "pas un dict")
    lignes = dashboard.lignes_reels([("Chloé", "Lucas", s), ("Chloé", "Lucas", None), ("Chloé", "Romaric", {"reels": []})],
                                    date(2026, 10, 20))
    assert lignes == [["2026-10-06", "Chloé", "Lucas", "1", "5", "1"]]


def test_deux_comptes_du_meme_gerant_additionnes():
    a = _serie({"publie": "2026-10-18T12:00:00+00:00", "vues": [["2026-10-19T12:00:00+00:00", 10]]})
    b = _serie({"publie": "2026-10-18T15:00:00+00:00", "vues": [["2026-10-19T12:00:00+00:00", 30]]})
    assert dashboard.lignes_reels([("Sophie", "Thia", a), ("Sophie", "Thia", b)], date(2026, 10, 20)) == \
        [["2026-10-18", "Sophie", "Thia", "2", "40", "2"]]
