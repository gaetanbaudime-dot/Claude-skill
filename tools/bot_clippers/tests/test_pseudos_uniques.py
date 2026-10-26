"""22/10 : @ « à créer » vérifiés sur Instagram, remplacés par une variante libre quand ils sont pris (stock seulement)."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instagram_rapidapi as I  # noqa: E402
import pseudos_uniques as P  # noqa: E402

T = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)


def test_variantes_valides_et_uniques():
    v = P.variantes("sophie.vanlife")
    assert v[:3] == ["sophie_vanlife", "sophie.vanlife_x", "x_sophie.vanlife"]
    assert all(P.valide(x) and x != "sophie.vanlife" for x in v) and len(v) == len(set(v))
    assert all(len(x) <= 30 for x in P.variantes("a" * 29)) and P.variantes("abcdefghijklmnopqrstuvwxyz1234")
    assert not P.valide(".abc") and not P.valide("abc.") and not P.valide("a..b") and not P.valide("A b")


def test_a_controler_stock_et_attribues():
    comptes = [{"onglet": "Sophie", "ligne": 5, "etat": "A CREER", "handle": "Sophie.Libre", "gerant": ""},
               {"onglet": "Sophie", "ligne": 6, "etat": "à créer", "handle": "sophie.thia", "gerant": "Thia"},
               {"onglet": "Sophie", "ligne": 7, "etat": "GOOD", "handle": "sophie.vivant", "gerant": "Thia"}]
    l = P.a_controler(comptes)
    assert [(x["handle"], x["stock"]) for x in l] == [("sophie.libre", True), ("sophie.thia", False)]


def test_a_revoir():
    assert P.a_revoir({}, "x", T)
    assert not P.a_revoir({"x": {"statut": "libre", "le": (T - timedelta(days=2)).isoformat()}}, "x", T)
    assert P.a_revoir({"x": {"statut": "libre", "le": (T - timedelta(days=9)).isoformat()}}, "x", T)
    assert not P.a_revoir({"x": {"statut": "pris", "le": (T - timedelta(days=30)).isoformat()}}, "x", T)


def test_passage_remplace_le_stock_pris_et_signale_l_attribue(monkeypatch):
    import google_api
    import onboarding
    import paie_clics
    import pilotage
    pris = {"sophie.prise", "sophie.thia", "sophie_prise"}               # la 1re variante (points → tirets bas) est prise aussi

    async def existe(session, h):
        return h in pris
    ecrit, onglets = [], {}

    async def sheets_ecrire_plusieurs(cl, ecritures):
        ecrit.extend(ecritures)
        return len(ecritures)

    async def ecrire(classeur, titre, entete, lignes):
        onglets[titre] = lignes
        return True

    async def classeur():
        return "U"
    monkeypatch.setattr(P, "existe", existe)
    monkeypatch.setattr(google_api, "sheets_ecrire_plusieurs", sheets_ecrire_plusieurs)
    monkeypatch.setattr(pilotage, "_ecrire", ecrire)
    monkeypatch.setattr(paie_clics, "_classeur_usage", classeur)
    monkeypatch.setattr(onboarding, "_colonnes_lues_par_onglet", {"Sophie": {"handle": 1}})
    I._jour.update({"jour": "", "n": 0, "restant": None})
    comptes = [{"onglet": "Sophie", "ligne": 5, "etat": "A CREER", "handle": "sophie.prise", "gerant": ""},
               {"onglet": "Sophie", "ligne": 6, "etat": "A CREER", "handle": "sophie.libre", "gerant": ""},
               {"onglet": "Sophie", "ligne": 7, "etat": "A CREER", "handle": "sophie.thia", "gerant": "Thia"}]

    async def lire_comptes():
        return [dict(c) for c in comptes]
    monkeypatch.setattr(onboarding, "lire_comptes", lire_comptes)
    store = {}
    b = asyncio.run(P.passage(None, store, comptes, T))
    assert (b["libres"], b["pris"], b["remplaces"], b["signales"]) == (1, 2, 1, 1)
    assert ecrit == [("Sophie!B5", [["sophie.prise_x"]])]               # seule la ligne du stock est réécrite
    assert store["pseudos"]["sophie.prise"]["remplace_par"] == "sophie.prise_x" and store["pseudos"]["sophie.prise_x"]["statut"] == "libre"
    statuts = {r[3]: r[4] for r in onglets[P.ONGLET]}
    assert statuts["sophie.thia"].startswith("pris, déjà attribué") and statuts["sophie.prise"] == "pris, remplacé dans le LOG"
    assert onglets[P.ONGLET][0][3] == "sophie.thia"                         # le problème à régler en haut
    ecrit.clear()
    asyncio.run(P.passage(None, store, comptes, T + timedelta(hours=8)))   # rien à revoir le même jour
    assert ecrit == []


def test_migration_par_id_quand_le_at_change():
    store = {"comptes": {"vieux.at": {"id": "77", "suivi": [["2026-10-20T00:00:00+00:00", 10, 3]], "historique_v2": "x"}},
             "reels": {"vieux.at": {"A": {"publie": "2026-10-20T00:00:00+00:00", "vues": 5}}}}
    assert I.migrer_par_id(store, "nouveau.at", "77") == "vieux.at"
    assert "vieux.at" not in store["comptes"] and store["comptes"]["nouveau.at"]["suivi"][0][1] == 10
    assert store["reels"]["nouveau.at"]["A"]["vues"] == 5 and I.migrer_par_id(store, "autre", "99") == ""
