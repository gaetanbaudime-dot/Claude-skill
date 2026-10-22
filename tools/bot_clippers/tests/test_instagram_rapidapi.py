"""22/10 : suivi Instagram RapidAPI (Instagram Looter)."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instagram_rapidapi as I  # noqa: E402

T = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def test_lire_profil_formats():
    a = {"pk": "123", "username": "x", "follower_count": 1500, "following_count": 10, "media_count": 42, "is_private": False}
    assert I.lire_profil(a) == {"id": "123", "username": "x", "followers": 1500, "suivis": 10, "publications": 42, "prive": False}
    b = {"data": {"user": {"id": "9", "username": "y", "edge_followed_by": {"count": 7}, "edge_owner_to_timeline_media": {"count": 3},
                           "is_private": True}}}
    p = I.lire_profil(b)
    assert (p["id"], p["followers"], p["publications"], p["prive"]) == ("9", 7, 3, True)


def test_lire_id_et_introuvable():
    assert I.lire_id({"status": True, "user_id": "4567"}) == "4567"
    assert I.lire_id({"status": False}) is None
    assert I.introuvable(404, None)
    assert I.introuvable(200, {"message": "User not found"})
    assert not I.introuvable(200, {"pk": 1})


def test_lire_reels_et_curseur():
    corps = {"items": [{"media": {"code": "A1", "taken_at": 1761134400, "play_count": 1000, "like_count": 50, "comment_count": 3}},
                       {"media": {"code": "A1", "taken_at": 1761134400}},
                       {"media": {"code": "B2", "taken_at": 1761048000, "ig_play_count": 20}}],
             "paging_info": {"max_id": "CUR", "more_available": True}}
    reels, cur = I.lire_reels(corps)
    assert [r["code"] for r in reels] == ["A1", "B2"] and reels[0]["vues"] == 1000 and reels[1]["vues"] == 20
    assert cur == "CUR"
    assert I.lire_reels({"items": [], "paging_info": {"max_id": "X", "more_available": False}})[1] is None


def test_fenetres_et_ecart():
    reels = {"a": {"publie": (T - timedelta(hours=5)).isoformat(), "vues": 100},
             "b": {"publie": (T - timedelta(days=10)).isoformat(), "vues": 50},
             "c": {"publie": (T - timedelta(days=45)).isoformat(), "vues": 7}}
    f = I.fenetres(reels, T)
    assert (f["reels1"], f["reels7"], f["reels15"], f["reels60"], f["vues15"], f["vues60"]) == (1, 1, 2, 3, 150, 157)
    suivi = [[(T - timedelta(hours=24)).isoformat(), 100, 5], [(T - timedelta(hours=8)).isoformat(), 110, 5], [T.isoformat(), 130, 6]]
    assert I.ecart(suivi, 24, T) == 30
    assert I.ecart(suivi[:1], 24, T) is None


def test_preuves_apres_creation():
    reels = [{"code": "A", "publie": (T - timedelta(days=1)).isoformat()}, {"code": "B", "publie": (T - timedelta(days=5)).isoformat()}]
    p = I.preuves(reels, T - timedelta(days=2))
    assert p == [{"code": "A", "publie": reels[0]["publie"], "type_verifie": "reel"}]


def test_comptes_a_suivre_et_types():
    comptes = [{"onglet": "Sophie", "handle": "sophie_vanlife", "etat": "GOOD", "gerant": "Sophie", "utilisation": "Compte de la créatrice"},
               {"onglet": "Sophie", "handle": "thia1", "etat": "GOOD", "gerant": "Thia", "utilisation": "Clipper"},
               {"onglet": "Sophie", "handle": "thia1", "etat": "GOOD", "gerant": "Thia"},
               {"onglet": "Sophie", "handle": "met1", "etat": "PRIVE", "gerant": "Rianah (Metricool)"},
               {"onglet": "Sophie", "handle": "mort", "etat": "BAN", "gerant": "X"},
               {"onglet": "Chloé", "handle": "neuf", "etat": "à créer", "gerant": "Y"}]
    s = I.comptes_a_suivre(comptes)
    assert [(x["handle"], x["type"]) for x in s] == [("sophie_vanlife", "Créatrice"), ("thia1", "Clipper"), ("met1", "Metricool")]


def test_lignes_et_top():
    suivis = [{"handle": "c1", "creatrice": "Sophie", "gerant": "Sophie", "type": "Créatrice"},
              {"handle": "k1", "creatrice": "Sophie", "gerant": "Thia", "type": "Clipper"}]
    store = {"comptes": {"c1": {"id": "1", "statut": "public", "suivi": [[T.isoformat(), 1000, 50]], "profil_le": "p", "reels_le": "r"},
                         "k1": {"statut": "introuvable"}},
             "reels": {"c1": {"X": {"publie": (T - timedelta(days=2)).isoformat(), "vues": 900},
                              "Y": {"publie": (T - timedelta(days=200)).isoformat(), "vues": 5000}}}}
    lignes = I.lignes_comptes(suivis, store, T)
    assert len(lignes[0]) == len(I.ENTETE_COMPTES) and lignes[0][6] == "1000" and lignes[0][11] == "1" and lignes[0][16] == "900"
    assert lignes[1][5] == "introuvable" and lignes[1][11] == ""         # jamais relu : vide, pas 0
    assert [r[4] for r in I.lignes_reels(suivis, store, T)] == ["X"]
    top = I.lignes_top(suivis, store)
    assert [t[3] for t in top] == ["https://www.instagram.com/reel/Y/", "https://www.instagram.com/reel/X/"]


def test_fusion_et_passage():
    d = I.fusionner_reels({"A": {"publie": "p", "vues": 10}}, [{"code": "A", "publie": "p", "vues": None, "likes": 3}], T)
    assert d["A"]["vues"] == 10 and d["A"]["likes"] == 3
    old = I.PASSAGES_HEURES
    try:
        I.PASSAGES_HEURES = [7, 14, 21]
        matin = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)      # 8 h à Paris
        assert I.passage_du({}, matin) == "2026-10-22-07"
        assert I.passage_du({"dernier_passage": "2026-10-22-07"}, matin) == ""
        assert I.passage_du({}, datetime(2026, 10, 22, 4, 0, tzinfo=timezone.utc)) == ""
    finally:
        I.PASSAGES_HEURES = old


def test_verser_preuves_dans_la_fiche_parcours():
    import parcours
    memoire = {"u1": {"dates": {"1_fait": (T - timedelta(days=3)).isoformat()}, "reels": {"h1": {"vus": 1}}}}
    ancien = dict(parcours._deps)
    try:
        parcours._deps.update({"lire_json": lambda f, d: memoire, "ecrire_json": lambda f, d: memoire.update(d), "FICHIER_PARCOURS": "x"})
        maintenant = datetime.now(timezone.utc)
        reels = [{"code": f"R{i}", "publie": (maintenant - timedelta(hours=i + 1)).isoformat(timespec="seconds")} for i in range(4)]
        reels.append({"code": "VIEUX", "publie": (maintenant - timedelta(days=10)).isoformat(timespec="seconds")})
        n = I.verser_preuves("u1", "h1", reels, maintenant - timedelta(days=3))
        assert n == 4                                                    # le Reel d'avant la création ne compte pas
        f = memoire["u1"]["reels"]["h1"]
        assert f["vus"] == 1 and sorted(f["reels_verifies_v2"]) == ["R0", "R1", "R2", "R3"] and f["source_rapidapi"]
        assert I.verser_preuves("u1", "h1", reels[:2], maintenant - timedelta(days=3)) == 4   # cumul, jamais en baisse
    finally:
        parcours._deps.clear(); parcours._deps.update(ancien)


def test_passage_complet_de_bout_en_bout(monkeypatch):
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    store = {}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    maintenant = datetime.now(timezone.utc)

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        if chemin == "/id":
            return 200, {"status": True, "user_id": "77"}
        if chemin == "/profile":
            return (404, {"message": "User not found"}) if params.get("username") == "mort" else \
                (200, {"pk": "77", "username": "thia1", "follower_count": 321, "media_count": 9, "is_private": False})
        if chemin == "/reels":
            t = int((maintenant - timedelta(days=1)).timestamp())
            return 200, {"items": [{"media": {"code": "Z9", "taken_at": t, "play_count": 4000}}],
                         "paging_info": {"more_available": False}}
        return 404, None

    async def lire_comptes():
        return [{"onglet": "Sophie", "handle": "thia1", "etat": "GOOD", "gerant": "Thia"},
                {"onglet": "Sophie", "handle": "mort", "etat": "GOOD", "gerant": "Benn"}]
    ecrits = {}

    async def ecrire(classeur, titre, entete, lignes):
        ecrits[titre] = lignes
        return True

    async def classeur():
        return "C"
    monkeypatch.setattr(I, "appeler", appeler)
    monkeypatch.setattr(onboarding, "lire_comptes", lire_comptes)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    bilan = asyncio.run(I.passage_complet(None))
    assert bilan["profils"] == 1 and bilan["reels"] == 1
    lignes = {l[3]: l for l in ecrits[I.ONGLET_COMPTES]}
    assert lignes["thia1"][6] == "321" and lignes["thia1"][12] == "1" and lignes["thia1"][17] == "4000"
    assert lignes["mort"][5] == "introuvable"
    assert ecrits[I.ONGLET_REELS][0][4] == "Z9"
