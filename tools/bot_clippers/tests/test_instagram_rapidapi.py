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
               {"onglet": "Chloé", "handle": "neuf", "etat": "à créer", "gerant": "Y"},
               {"onglet": "Sarah", "handle": "appel1", "etat": "Faire appel", "gerant": "Yves"},          # 26/10 : comptes en appel suivis
               {"onglet": "Sarah", "handle": "appel2", "etat": "APPEL A FAIRE", "gerant": "Yves"}]
    s = I.comptes_a_suivre(comptes)
    assert [(x["handle"], x["type"]) for x in s] == [("sophie_vanlife", "Créatrice"), ("thia1", "Clipper"), ("met1", "Metricool"),
                                                     ("appel1", "Clipper"), ("appel2", "Clipper")]


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


def test_page_pleine_sans_suite_notee(monkeypatch):
    import asyncio
    maintenant = datetime.now(timezone.utc)
    store = {"comptes": {"k1": {"id": "77"}}}

    async def appeler(session, chemin, params):
        items = [{"media": {"code": f"R{k}", "taken_at": int((maintenant - timedelta(hours=k)).timestamp())}} for k in range(12)]
        return 200, {"items": items, "status": "ok", "paging_info": {"more_available": False}}
    monkeypatch.setattr(I, "appeler", appeler)
    I._diag.update({"pages": 0, "echecs": {}, "sans_suite": {}})
    asyncio.run(I.relire_reels(None, store, "k1", maintenant, jusqu_a=maintenant - timedelta(days=15), pages=4))
    assert I._diag["sans_suite"]["k1"]["paging"] == {"more_available": False}
    l = I.lignes_passages([{"debut": "a", "sans_suite": dict(I._diag["sans_suite"])}])
    assert l[0][12].startswith("k1 ") and "more_available" in l[0][12]


def test_page_suivante_avec_le_meme_compte_flashapi(monkeypatch):
    """Diagnostic du 23/10 : le curseur n'est valable que sur le compte FlashAPI qui a servi la page (pagination.id_acc).
    Sans id_acc, la page 2 revient vide avec un message ; avec, la liste continue jusqu'à la fenêtre demandée."""
    import asyncio
    maintenant = datetime.now(timezone.utc)
    store, appels = {"comptes": {"k1": {"id": "77"}}}, []

    def page(debut):
        return [{"media": {"code": f"R{debut + k}", "taken_at": int((maintenant - timedelta(days=(debut + k) / 4)).timestamp()),
                           "ig_play_count": 10}} for k in range(12)]

    async def appeler(session, chemin, params):
        appels.append((params.get("max_id"), params.get("id_acc")))
        cur = params.get("max_id")
        if cur and params.get("id_acc") != "355671":
            return 200, {"message": "Not found", "pagination": {"id_acc": 1}, "status": "ok"}     # autre compte : curseur inconnu
        n = 0 if not cur else int(cur[1:])
        return 200, {"items": page(n), "paging_info": {"max_id": f"P{n + 12}", "more_available": True},
                     "pagination": {"id_acc": 355671}, "status": "ok"}
    monkeypatch.setattr(I, "appeler", appeler)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    I._diag.update({"pages": 0, "echecs": {}, "sans_suite": {}, "curseur_perdu": {}})
    reels = asyncio.run(I.relire_reels(None, store, "k1", maintenant, jusqu_a=maintenant - timedelta(days=15), pages=10))
    assert appels[0] == (None, None) and all(a == "355671" for _, a in appels[1:])
    assert len(reels) == 72 and not store["comptes"]["k1"]["fin_api"]       # 6 pages : la 6e dépasse 15 jours (4 Reels par jour)
    assert I._diag["curseur_perdu"] == {}


def test_curseur_perdu_reessaye_puis_note(monkeypatch):
    import asyncio
    maintenant = datetime.now(timezone.utc)
    store, appels = {"comptes": {"k1": {"id": "77"}}}, []

    async def appeler(session, chemin, params):
        appels.append(params.get("max_id"))
        if params.get("max_id"):
            return 200, {"message": "Not found", "pagination": {"id_acc": 9}, "status": "ok"}
        items = [{"media": {"code": f"R{k}", "taken_at": int((maintenant - timedelta(hours=k)).timestamp())}} for k in range(12)]
        return 200, {"items": items, "paging_info": {"max_id": "P2", "more_available": True}, "pagination": {"id_acc": 5}}

    async def rien(*a, **k):
        return None
    monkeypatch.setattr(I, "appeler", appeler)
    monkeypatch.setattr(asyncio, "sleep", rien)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    I._diag.update({"pages": 0, "echecs": {}, "sans_suite": {}, "curseur_perdu": {}})
    asyncio.run(I.relire_reels(None, store, "k1", maintenant, jusqu_a=maintenant - timedelta(days=15), pages=4))
    assert appels == [None, "P2", "P2"] and I._diag["curseur_perdu"]["k1"]["page"] == 2
    assert len(store["reels"]["k1"]) == 12 and I._diag["echecs"] == {}
    assert I.curseur_texte(I._diag["curseur_perdu"]).startswith("k1 (page 2, Not found)")


def test_page_1_vide_reessayee_et_compte_pas_marque_relu(monkeypatch):
    import asyncio
    maintenant = datetime.now(timezone.utc)
    vide = (200, {"items": [], "paging_info": {"more_available": False}, "pagination": {"id_acc": 3}, "status": "ok"})
    plein = (200, {"items": [{"media": {"code": "N1", "taken_at": int(maintenant.timestamp())}}],
                   "paging_info": {"more_available": False}, "pagination": {"id_acc": 4}})

    async def rien(*a, **k):
        return None
    monkeypatch.setattr(asyncio, "sleep", rien)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    for reponses, attendu in (([vide, vide, vide], None), ([vide, plein], "N1")):
        store = {"comptes": {"k1": {"id": "77", "suivi": [["t", 10, 40]]}}, "reels": {"k1": {"OLD": {"publie": "2026-01-01T00:00:00+00:00"}}}}
        file = list(reponses)

        async def appeler(session, chemin, params):
            return file.pop(0)
        monkeypatch.setattr(I, "appeler", appeler)
        I._diag.update({"pages": 0, "echecs": {}, "sans_suite": {}, "curseur_perdu": {}})
        asyncio.run(I.relire_reels(None, store, "k1", maintenant, pages=4))
        if attendu is None:
            assert "reels_le" not in store["comptes"]["k1"] and I._diag["curseur_perdu"]["k1"]["page"] == 1 and not file
        else:
            assert attendu in store["reels"]["k1"] and store["comptes"]["k1"]["reels_le"]
    assert not I.a_des_reels({"comptes": {"n": {"suivi": [["t", 0, 0]]}}}, "n")      # compte vide pour de vrai : pas d'essai
    assert not I.a_des_reels({"comptes": {"p": {"statut": "privé", "suivi": [["t", 9, 45]]}}}, "p")


def test_compte_prive_sans_requete_de_reels(monkeypatch):
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    store = {}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    chemins = []

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        chemins.append(chemin)
        if chemin == I.API["id"][0]:
            return 200, {"id": 77, "status": "ok"}
        return 200, {"user": {"pk": 77, "username": "p1", "follower_count": 40, "media_count": 45, "is_private": True}}

    async def lire_comptes():
        return [{"onglet": "Sarah", "handle": "p1", "etat": "GOOD", "gerant": "Simon"}]

    async def ecrire(classeur, titre, entete, lignes):
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
    assert I.API["reels"][0] not in chemins and bilan["rattrapage_restants"] == 0
    assert store["d"]["comptes"]["p1"]["statut"] == "privé" and store["d"]["comptes"]["p1"]["rattrapage_j"] == 180


def test_premier_passage_de_la_correction_relit_tout(monkeypatch):
    """Store d'avant la correction du curseur : chaque compte repart en rattrapage sur 180 jours, la route des publications
    est oubliée ; un store neuf n'est pas touché."""
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    maintenant = datetime.now(timezone.utc)
    store = {"d": {"comptes": {"k1": {"id": "77", "rattrapage_j": 180, "route": "posts", "fin_pleine": True, "historique_v2": "x"}},
                   "etat": {"route_posts": {"chemin": "/ig/posts/"}, "dernier_rattrapage": {"jours": 180}}}}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    pages = []

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        if chemin == I.API["profil"][0]:
            return 200, {"user": {"pk": 77, "username": "k1", "follower_count": 5, "media_count": 30, "is_private": False}}
        pages.append(params.get("max_id"))
        j = {None: 2, "P2": 100}.get(params.get("max_id"), 200)
        nxt = {None: "P2", "P2": "P3"}.get(params.get("max_id"))
        return 200, {"items": [{"media": {"code": f"C{j}", "taken_at": int((maintenant - timedelta(days=j)).timestamp())}}],
                     "paging_info": {"max_id": nxt, "more_available": bool(nxt)}, "pagination": {"id_acc": 4}}

    async def lire_comptes():
        return [{"onglet": "Sophie", "handle": "k1", "etat": "GOOD", "gerant": "Thia"}]

    async def ecrire(classeur, titre, entete, lignes):
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
    d = store["d"]
    assert pages == [None, "P2", "P3"] and d["etat"]["pagination_v"] == I.PAGINATION_V and "route_posts" not in d["etat"]
    assert d["comptes"]["k1"]["rattrapage_j"] == 180 and "route" not in d["comptes"]["k1"] and d["etat"]["dernier_rattrapage"]["fini"]
    pages.clear()
    asyncio.run(I.passage_complet(None))                                  # version déjà appliquée : suivi léger (15 jours)
    assert pages == [None, "P2"]


def test_publications_jamais_sous_les_reels_connus():
    T0 = datetime(2026, 10, 23, 6, 0, tzinfo=timezone.utc)
    suivis = [{"handle": "k1", "creatrice": "Sarah", "gerant": "Yves", "type": "Clipper"}]
    reels = {f"R{k}": {"publie": (T0 - timedelta(days=k)).isoformat(), "vues": 10} for k in range(16)}
    store = {"comptes": {"k1": {"suivi": [["t", 156, 1]], "reels_le": "x"}}, "reels": {"k1": reels}}
    assert I.lignes_comptes(suivis, store, T0)[0][9] == "16"
    store["comptes"]["k1"]["suivi"] = [["t", 156, 40]]
    assert I.lignes_comptes(suivis, store, T0)[0][9] == "40"


def test_passage_sans_aucune_lecture_n_ecrase_pas_les_onglets(monkeypatch):
    """24/10 : une clé sans accès (403 partout) ne doit pas réécrire les onglets avec un historique vide."""
    import asyncio
    import onboarding
    import paie_clics
    import pilotage
    store = {}
    I.configurer({"lire_json": lambda f, d: store.get("d", d), "ecrire_json": lambda f, d: store.__setitem__("d", d), "FICHIER": "x"})
    ecrits = []

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        return 403, {"message": "You are not subscribed to this API."}

    async def lire_comptes():
        return [{"onglet": "Sophie", "handle": "k1", "etat": "GOOD", "gerant": "Thia"}]

    async def ecrire(classeur, titre, entete, lignes):
        ecrits.append(titre)
        return True

    async def classeur():
        return "C"
    monkeypatch.setattr(I, "appeler", appeler)
    monkeypatch.setattr(I, "RATTRAPAGE_J", 0)
    monkeypatch.setattr(onboarding, "lire_comptes", lire_comptes)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    bilan = asyncio.run(I.passage_complet(None))
    assert bilan["onglets_ecrits"] is False and not any(t.startswith("IG · ") and t != "IG · Reels Metricool" for t in ecrits)


def test_compte_a_creer_vu_libre_suivi_des_qu_il_existe(monkeypatch):
    """27/10 : un @ « à créer » attribué, vu libre, est suivi ; tant qu'il n'existe pas il n'a pas de ligne ; créé, il est relu
    et marqué « créé ». Un @ du stock ou déjà pris avant n'est pas suivi."""
    comptes = [{"onglet": "Sarah", "handle": "neuf", "etat": "à créer", "gerant": "Mavie"},
               {"onglet": "Sarah", "handle": "stock1", "etat": "à créer", "gerant": ""},
               {"onglet": "Sarah", "handle": "pris1", "etat": "à créer", "gerant": "Mavie"}]
    store = {"pseudos": {"neuf": {"statut": "libre"}, "stock1": {"statut": "libre"}, "pris1": {"statut": "pris", "attribue": True}}}
    s = I.comptes_a_suivre(comptes, I.crees_possibles(store))
    assert [(x["handle"], x.get("a_creer")) for x in s] == [("neuf", True)]
    T0 = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
    assert I.lignes_comptes(s, {"comptes": {"neuf": {"statut": "introuvable"}}}, T0) == []
    assert I.lignes_comptes(s, {"comptes": {"neuf": {"statut": "public", "suivi": [["t", 1, 0]]}}}, T0)[0][3] == "neuf"


def test_variantes_instagram_comme_les_suggestions_du_27_10():
    v = I.variantes_instagram("sarah.clic")
    assert v[:3] == ["sara.hclic", "sara_hclic", "sar.ahclic"] and "sarah_clic" in v
    assert all(I.RE_HANDLE.match(x) for x in v)


def test_variante_creee_seulement_si_unique_et_neuve():
    neuf = {"statut": "existe", "id": 9, "followers": 2, "publications": 0, "bio": "Fan de Sarah 💛 Ses meilleurs moments, chaque jour"}
    vieux = {"statut": "existe", "id": 8, "followers": 5000, "publications": 300}
    rien = {"statut": "introuvable"}
    assert I.variante_creee({"sara_hclic": neuf, "sara.hclic": rien}, "Sarah") == ("sara_hclic", True)
    assert I.variante_creee({"sara_hclic": neuf, "sara.hclic": dict(neuf, id=10)}, "Sarah") is None   # deux comptes : on ne choisit pas
    assert I.variante_creee({"sara_hclic": vieux}, "Sarah") is None                                    # compte installé : pas le sien
    assert I.variante_creee({"sara_hclic": dict(neuf, bio="")}, "Sarah") == ("sara_hclic", False)     # sans preuve : proposé
    assert I.variante_creee({"sara_hclic": dict(neuf, bio=""), "sarah_clic": dict(vieux, followers=208, publications=40)},
                            "Sarah") == ("sara_hclic", False)                                          # l'installé ne bloque pas


def test_preuve_a_nous():
    assert I.preuve_a_nous({"bio": "Fan de Jade 💛 Ses meilleurs moments, chaque jour"}, "Jade")
    assert I.preuve_a_nous({"bio": "Chloé, 34 ans 🤍 Marseille"}, "Chloé")
    assert I.preuve_a_nous({"statut": "privé", "bio": "Par ici 👇", "liens": ["https://sarah-ivanova.fr/5"]}, "Sarah")
    assert not I.preuve_a_nous({"statut": "privé", "bio": "Secret 🌴", "liens": []}, "Sarah")       # le faux rattachement du 27/10
    assert not I.preuve_a_nous({"bio": "", "nom": ""}, "Sarah")
    assert not I.preuve_a_nous({"bio": "Sarahlove forever"}, "Sarah")                                  # un mot entier, pas un morceau


def test_detacher_sans_preuve():
    store = {"comptes": {"daily_sarah_x": {"id": "46", "statut": "privé", "renomme_en": "daily.sarah.x", "variante_creee": "daily.sarah.x",
                                           "bio": "Secret 🌴", "liens": []}},
             "pseudos": {"daily_sarah_x": {"statut": "cree", "cree_sous": "daily.sarah.x", "le": "2026-10-22T09:16:20+00:00"},
                         "daily.sarah.x": {"statut": "cree", "variante_de": "daily_sarah_x"}}, "reels": {"daily_sarah_x": {"X": {}}}}
    suivis = [{"handle": "daily_sarah_x", "creatrice": "Sarah", "a_creer": True}]
    assert I.detacher_sans_preuve(store, suivis) == ["daily_sarah_x"]
    e = store["comptes"]["daily_sarah_x"]
    assert "id" not in e and "renomme_en" not in e and e["statut"] == "introuvable" and "daily_sarah_x" not in store["reels"]
    assert store["pseudos"]["daily_sarah_x"]["statut"] == "libre" and store["pseudos"]["daily_sarah_x"]["propose"] == "daily.sarah.x"
    assert "daily.sarah.x" not in store["pseudos"]


def test_compte_a_creer_retrouve_sous_la_suggestion_instagram(monkeypatch):
    """27/10 : @ prévu libre pour l'API mais refusé par Instagram ; le clipper prend la 2e suggestion ; le suivi la retrouve,
    se rattache à son ID et la relit (Renommé en)."""
    import asyncio
    maintenant = datetime.now(timezone.utc)
    store = {"pseudos": {"sarah.clic": {"statut": "libre"}}, "comptes": {"sarah.clic": {"statut": "introuvable"}}}
    suivis = [{"handle": "sarah.clic", "creatrice": "Sarah", "gerant": "Andrianina", "type": "Clipper", "a_creer": True}]

    async def appeler(session, chemin, params):
        I._jour["n"] += 1
        if chemin == I.API["id"][0]:
            return (200, {"status": True, "user_id": "99"}) if params.get("user") == "sara_hclic" else (404, {"message": "User not found"})
        if chemin == I.API["profil"][0]:
            return 200, {"user": {"pk": 99, "username": "sara_hclic", "follower_count": 2, "media_count": 0, "is_private": False,
                                  "biography": "Compte fan de Sarah 🌸 Bonne humeur garantie"}}
        return 200, {"items": [], "paging_info": {"more_available": False}}
    monkeypatch.setattr(I, "appeler", appeler)
    I._jour.update({"jour": "", "n": 0, "restant": None})
    b = asyncio.run(I.chercher_variantes(None, store, suivis, maintenant))
    e = store["comptes"]["sarah.clic"]
    assert b["existantes"] == 1 and e["id"] == "99" and e["renomme_en"] == "sara_hclic" and e["statut"] == "public"
    assert store["pseudos"]["sarah.clic"]["statut"] == "cree" and store["pseudos"]["sarah.clic"]["cree_sous"] == "sara_hclic"
    assert "sara_hclic" in I.crees_possibles(store)                       # renommé par le bot : toujours suivi sous son nouvel @
    assert I.lignes_comptes(suivis, store, maintenant)[0][22] == "sara_hclic"
