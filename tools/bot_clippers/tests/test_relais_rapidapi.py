"""21/10 : relais de test RapidAPI (onglet « Test API Instagram »)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import relais_rapidapi as R  # noqa: E402


def test_hotes_autorises():
    assert R.hote_autorise("instagram-looter2.p.rapidapi.com")
    assert not R.hote_autorise("evil.example.com")
    assert not R.hote_autorise("x.p.rapidapi.com/../")
    assert not R.hote_autorise("")


def test_demandes():
    lignes = [["fait", "a.p.rapidapi.com", "x"], ["à faire", "a.p.rapidapi.com", "profile", "?username=foo&n=2", "", ""],
              ["", "a.p.rapidapi.com", "y"], ["A faire", "b.p.rapidapi.com", "/reels", "id=1", "post", "{}"]]
    assert R.demandes(lignes) == [(3, "a.p.rapidapi.com", "/profile", {"username": "foo", "n": "2"}, "GET", ""),
                                  (5, "b.p.rapidapi.com", "/reels", {"id": "1"}, "POST", "{}")]


def test_reponse_tronquee():
    assert R.reponse_texte('{"a": 1}') == '{"a":1}'
    long = R.reponse_texte("x" * (R.TAILLE_MAX + 10))
    assert long.endswith("caractères]") and len(long) < R.TAILLE_MAX + 60
