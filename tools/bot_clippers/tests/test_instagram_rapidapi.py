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
        if chemin == I.API["id"][0]:
            nom = params.get("user") or params.get("username")
            return (404, {"message": "User not found"}) if nom == "mort" else (200, {"status": True, "user_id": "77"})
        if chemin == I.API["profil"][0]:
            return 200, {"pk": "77", "username": "thia1", "follower_count": 321, "media_count": 9, "is_private": False}
        if chemin == I.API["reels"][0]:
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


def test_reponse_flashapi_reelle_vues_instagram_et_epingles():
    """Forme relevée le 22/10 sur FlashAPI /ig/reels_posts/ : items[].media, deux Reels épinglés anciens en tête,
    play_count = Instagram + Facebook, ig_play_count = Instagram seul."""
    corps = {"items": [{"media": {"code": "EP1", "taken_at": 1701680179, "play_count": 2038380, "ig_play_count": 96062,
                                  "fb_play_count": 1942318, "clips_tab_pinned_user_ids": [5950185985], "timeline_pinned_user_ids": []}},
                       {"media": {"code": "NEUF", "taken_at": int((T - timedelta(days=3)).timestamp()), "play_count": 500,
                                  "ig_play_count": 0, "clips_tab_pinned_user_ids": []}},
                       {"media": {"code": "SANSIG", "taken_at": int((T - timedelta(days=5)).timestamp()), "play_count": 700}}],
             "paging_info": {"max_id": "QVFD", "more_available": True}, "status": "ok"}
    reels, cur = I.lire_reels(corps)
    vues = {r["code"]: r["vues"] for r in reels}
    assert vues == {"EP1": 96062, "NEUF": 0, "SANSIG": 700}              # 0 lecture Instagram reste 0, pas play_count
    assert [r["code"] for r in reels if r["epingle"]] == ["EP1"] and cur == "QVFD"
    # l'épinglé de 2023 n'arrête pas la reprise d'historique : le plus ancien compté est le Reel d'il y a 5 jours
    assert I.plus_ancien(reels) == T - timedelta(days=5)
    assert I.plus_ancien([r for r in reels if r["epingle"]]) > T      # page d'épinglés seulement : on continue


def test_top_sur_365_jours_sans_vieil_epingle():
    suivis = [{"handle": "c1", "creatrice": "Sophie", "gerant": "Sophie", "type": "Créatrice"}]
    store = {"reels": {"c1": {"VIEUX": {"publie": (T - timedelta(days=700)).isoformat(), "vues": 9_000_000, "epingle": True},
                              "AN": {"publie": (T - timedelta(days=300)).isoformat(), "vues": 40_000},
                              "MOIS": {"publie": (T - timedelta(days=20)).isoformat(), "vues": 12_000}}}}
    assert [t[3].split("/")[-2] for t in I.lignes_top(suivis, store, maintenant=T)] == ["AN", "MOIS"]
    assert [t[3].split("/")[-2] for t in I.lignes_top(suivis, store, maintenant=T, jours=180)] == ["MOIS"]


def test_echantillon_garde_la_fin_de_reponse():
    import json as _j
    long = _j.dumps({"items": ["x" * 100000], "paging_info": {"max_id": "FIN", "more_available": True}})
    t = I._debut_et_fin(long)
    assert len(t) < 46000 and '"max_id":"FIN"' in t and "milieu coupé" in t
    assert I._debut_et_fin('{"a":1}') == '{"a":1}'


def test_clipper_relu_sur_15_jours_en_plusieurs_pages(monkeypatch):
    """Page 1 = 12 Reels récents (dont un épinglé ancien) : on tourne la page jusqu'à dépasser 15 jours, 4 pages au plus."""
    import asyncio
    maintenant = datetime.now(timezone.utc)
    store, appels = {"comptes": {"k1": {"id": "77"}}}, []

    def page(debut, n):
        return [{"media": {"code": f"R{debut + k}", "taken_at": int((maintenant - timedelta(days=debut + k)).timestamp()),
                           "ig_play_count": 10}} for k in range(n)]

    async def appeler(session, chemin, params):
        appels.append(params.get("max_id"))
        if not params.get("max_id"):
            vieux = {"media": {"code": "EPI", "taken_at": 1701680179, "ig_play_count": 9, "clips_tab_pinned_user_ids": [77]}}
            return 200, {"items": [vieux] + page(0, 11), "paging_info": {"max_id": "P2", "more_available": True}}
        if params["max_id"] == "P2":
            return 200, {"items": page(11, 12), "paging_info": {"max_id": "P3", "more_available": True}}
        return 200, {"items": page(23, 12), "paging_info": {"max_id": "P4", "more_available": True}}
    monkeypatch.setattr(I, "appeler", appeler)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    asyncio.run(I.relire_reels(None, store, "k1", maintenant, jusqu_a=maintenant - timedelta(days=15), pages=4))
    assert appels == [None, "P2"]                                        # page 2 atteint 22 jours : arrêt, l'épinglé n'a pas compté
    assert I.fenetres(store["reels"]["k1"], maintenant)["reels15"] == 15   # jours 0 à 14 (le 15e tombe juste au-delà)


def test_rattrapage_180_jours_repris_puis_fini(monkeypatch):
    """Rattrapage : chaque compte relu jusqu'à 180 jours (pages successives), marqué fait, puis le suivi léger reprend."""
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    store = {}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    maintenant = datetime.now(timezone.utc)
    pages_lues = []

    def media(code, j):
        return {"media": {"code": code, "taken_at": int((maintenant - timedelta(days=j)).timestamp()), "ig_play_count": 100}}

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        if chemin == I.API["id"][0]:
            return 200, {"id": 77, "status": "ok"}
        if chemin == I.API["profil"][0]:
            return 200, {"user": {"pk": 77, "username": "k1", "follower_count": 0, "media_count": 30, "is_private": False}}
        cur = params.get("max_id")
        pages_lues.append(cur)
        if not cur:
            return 200, {"items": [media("A", 1), media("B", 20)], "paging_info": {"max_id": "P2", "more_available": True}}
        if cur == "P2":
            return 200, {"items": [media("C", 100)], "paging_info": {"max_id": "P3", "more_available": True}}
        return 200, {"items": [media("D", 200)], "paging_info": {"max_id": "P4", "more_available": True}}

    async def lire_comptes():
        return [{"onglet": "Sophie", "handle": "k1", "etat": "GOOD", "gerant": "Thia"}]
    ecrits = {}

    async def ecrire(classeur, titre, entete, lignes):
        ecrits[titre] = lignes
        return True

    async def classeur():
        return "C"
    monkeypatch.setattr(I, "appeler", appeler)
    monkeypatch.setattr(I, "RATTRAPAGE_J", 180)
    monkeypatch.setattr(onboarding, "lire_comptes", lire_comptes)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    bilan = asyncio.run(I.passage_complet(None))
    assert pages_lues == [None, "P2", "P3"] and bilan["rattrapage_restants"] == 0
    d = store["d"]
    assert d["comptes"]["k1"]["rattrapage_j"] == 180 and "rattrapage" not in d["etat"] and d["etat"]["dernier_rattrapage"]["fini"]
    assert sorted(r[4] for r in ecrits[I.ONGLET_ARCHIVE]) == ["A", "B", "C"]     # 200 jours : hors archive 180 j
    assert sorted(r[4] for r in ecrits[I.ONGLET_REELS]) == ["A", "B"]           # l'onglet du Cockpit garde 60 jours
    assert ecrits[I.ONGLET_PASSAGES][0][5] == "3" and ecrits[I.ONGLET_PASSAGES][0][9] == "180 j : fini"
    assert ecrits[I.ONGLET_COMPTES][0][6] == "0"                               # 0 follower affiché
    # passage suivant, sans champ rattrapage : suivi léger (15 jours, s'arrête dès la page 1 qui dépasse 15 jours)
    monkeypatch.setattr(I, "RATTRAPAGE_J", 0)
    pages_lues.clear()
    asyncio.run(I.passage_complet(None))
    assert pages_lues == [None]


def test_appeler_retente_une_fois_sur_429(monkeypatch):
    import asyncio
    codes = [429, 200]

    class Rep:
        def __init__(self, c):
            self.status, self.headers = c, {"x-ratelimit-requests-remaining": "4000"}

        async def text(self):
            return '{"ok": true}'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Session:
        def get(self, *a, **k):
            return Rep(codes.pop(0))

    async def rien(*a, **k):
        return None
    monkeypatch.setattr(I, "_echantillon", rien)
    monkeypatch.setattr(I, "PAUSE", 0)
    monkeypatch.setattr(asyncio, "sleep", rien)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    assert asyncio.run(I.appeler(Session(), "/x", {})) == (200, {"ok": True}) and I._jour["n"] == 2 and I._jour["restant"] == 4000


def test_a_rattraper_et_journal():
    assert I.a_rattraper({}, 180) and not I.a_rattraper({"rattrapage_j": 180}, 180) and not I.a_rattraper({}, 0)
    assert I.a_rattraper({"rattrapage_j": 90}, 180)
    l = I.lignes_passages([{"debut": "a", "echecs": {}}, {"debut": "b", "echecs": {"429": 2, "réseau": 1}, "arret": "temps"}])
    assert l[0][0] == "b" and l[0][6] == "429 : 2 · réseau : 1" and l[0][10] == "temps" and l[1][6] == "0"


def test_fenetre_45_jours_une_fois_par_jour(monkeypatch):
    """1er passage du jour : relecture jusqu'à 45 jours (vues des Reels plus anciens à jour) ; les suivants : 15 jours."""
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    store = {}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    maintenant = datetime.now(timezone.utc)
    pages = []

    def media(code, j):
        return {"media": {"code": code, "taken_at": int((maintenant - timedelta(days=j)).timestamp()), "ig_play_count": 10}}

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        if chemin == I.API["id"][0]:
            return 200, {"id": 77, "status": "ok"}
        if chemin == I.API["profil"][0]:
            return 200, {"user": {"pk": 77, "username": "k1", "follower_count": 5, "media_count": 30, "is_private": False}}
        cur = params.get("max_id"); pages.append(cur)
        suite = {None: ([media("A", 2), media("B", 20)], "P2"), "P2": ([media("C", 40)], "P3"), "P3": ([media("D", 70)], "P4")}
        items, nxt = suite.get(cur, ([media("E", 90)], None))
        return 200, {"items": items, "paging_info": {"max_id": nxt, "more_available": bool(nxt)}}

    async def lire_comptes():
        return [{"onglet": "Sophie", "handle": "k1", "etat": "GOOD", "gerant": "Thia"}]
    ecrits = {}

    async def ecrire(classeur, titre, entete, lignes):
        ecrits[titre] = lignes
        return True

    async def classeur():
        return "C"
    monkeypatch.setattr(I, "appeler", appeler)
    monkeypatch.setattr(I, "RATTRAPAGE_J", 0)
    monkeypatch.setattr(onboarding, "lire_comptes", lire_comptes)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    asyncio.run(I.passage_complet(None))
    assert pages == [None, "P2", "P3"] and ecrits[I.ONGLET_PASSAGES][0][11] == "45 j"   # s'arrête après avoir dépassé 45 jours
    pages.clear()
    asyncio.run(I.passage_complet(None))
    assert pages == [None] and ecrits[I.ONGLET_PASSAGES][0][11] == "15 j"               # même jour : 15 jours, page 1 suffit
