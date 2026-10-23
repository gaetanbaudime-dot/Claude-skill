"""22/10 : Reels des comptes branchés à Metricool versés dans le suivi Instagram (onglet d'import et API REST)."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import metricool_reels as R  # noqa: E402

T = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def test_lignes_import_et_fusion():
    v = [["@", "Code", "Lien", "Publié le", "Vues", "Likes", "Commentaires", "Relu le"],
         ["@ItsVan", "A1", "", "2026-10-20T14:09:53+00:00", "4 750", "72", "5", ""],
         ["itsvan", "", "", "2026-10-20T14:09:53+00:00", "1", "", "", ""],                # sans code : ignoré
         ["itsvan", "B2", "", "2026-09-01T10:00:00+00:00", "", "", "", ""]]
    l = R.lignes_import(v)
    assert [(x["handle"], x["code"], x["vues"]) for x in l] == [("itsvan", "A1", 4750), ("itsvan", "B2", None)]
    store = {"reels": {"itsvan": {"A1": {"publie": "2026-10-20T14:09:53+00:00", "vues": 4926}}}}
    assert R.fusionner(store, "itsvan", l, T) == 1                                       # B2 ajouté, A1 déjà là
    assert store["reels"]["itsvan"]["A1"]["vues"] == 4926                                # la plus grande valeur gardée
    assert store["reels"]["itsvan"]["B2"].get("vues") is None and store["reels"]["itsvan"]["B2"]["metricool"]
    assert [r[1] for r in R.lignes_onglet(store)] == ["A1", "B2"]


def test_passage_import_puis_rest(monkeypatch):
    import google_api
    import metricool_comptes as M
    import paie_clics
    import pilotage
    onglets = {}

    async def classeur():
        return "U"

    async def lire(cl, plage):
        return [["@", "Code", "Publié le", "Vues"], ["itsvan", "OLD", "2026-06-01T10:00:00+00:00", "999"],
                ["inconnu", "X", "2026-06-01T10:00:00+00:00", "5"]]

    async def ecrire(cl, titre, entete, lignes):
        onglets[titre] = lignes
        return True

    async def get(route, params):
        return {"data": [{"id": 6192908, "label": "Sophie 1", "timezone": "Europe/Paris", "networksData": {"instagramData": "itsvan"}}]}
    fenetres = []

    async def publications(mq, debut, fin):
        fenetres.append((fin - debut).days)
        return []

    def reels_de(pubs, tz, debut, fin):
        return [{"code": f"N{k}", "publie": (fin - timedelta(days=k)).isoformat(), "vues": 100 + k} for k in range(3)], {}, {}, 0
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    monkeypatch.setattr(google_api, "actif", lambda: True)
    monkeypatch.setattr(google_api, "sheets_lire", lire)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(M, "METRICOOL_API_KEY", "k")
    monkeypatch.setattr(M, "_get", get)
    monkeypatch.setattr(M, "_publications", publications)
    monkeypatch.setattr(M, "reels_de", reels_de)
    store = {}
    b = asyncio.run(R.passage(store, [{"handle": "itsvan"}], T, longue=False))
    assert b["importes"] == 1 and b["ajoutes"] == 4 and set(store["reels"]["itsvan"]) == {"OLD", "N0", "N1", "N2"}
    assert fenetres == [180] and "itsvan (3 Reels sur 180 j)" in b["rest"]
    asyncio.run(R.passage(store, [{"handle": "itsvan"}], T, longue=False))
    asyncio.run(R.passage(store, [{"handle": "itsvan"}], T, longue=True))
    assert fenetres == [180, 10, 45]                                                     # 180 j une fois, puis 10 / 45
    assert len(onglets[R.ONGLET]) == 4


def test_sans_cle_rien_ne_casse(monkeypatch):
    import metricool_comptes as M
    import paie_clics

    async def classeur():
        return None
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    monkeypatch.setattr(M, "METRICOOL_API_KEY", "")
    b = asyncio.run(R.passage({}, [{"handle": "x"}], T))
    assert b["rest"].startswith("sans clé")
