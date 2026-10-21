"""21/10 : le rapport Telegram en cinq lignes, avec les chiffres du Cockpit Clipping."""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rapport_quotidien as rq  # noqa: E402

HIER = date(2026, 10, 20)


def onglets(saisi="oui"):
    subs = [["Jour", "Créatrice", "Subs OF", "CA OF ($)", "Subs MYM", "CA MYM (€)", "Saisi"]]
    for j in range(1, 15):
        subs.append([f"2026-10-{20 - j + 1:02d}", "Sophie", "10", "100", "20", "50", saisi if j == 1 else "oui"])
        subs.append([f"2026-10-{20 - j + 1:02d}", "Chloé", "5", "50", "5", "10", "oui"])
    clics = [["Jour", "Créatrice", "Axe", "Source", "Qui", "Visites payables", "Visites hors robots", "Liens", "Liens non relevés"],
             ["2026-10-20", "Chloé", "Vertical", "Bio Instagram", "chloe.fr", "60", "61", "1", "0"],
             ["2026-10-20", "Sophie", "Horizontal", "Clipper", "Mathieu", "40", "41", "1", "0"],
             ["2026-10-21", "Sophie", "Horizontal", "Clipper", "Mathieu", "999", "0", "1", "0"]]
    reels = [["Jour", "Créatrice", "Gérant", "Reels", "Vues (dernier relevé)", "Reels mesurés"],
             ["2026-10-20", "Sophie", "Rianah (Metricool)", "10", "100", "10"], ["2026-10-20", "Sophie", "Mathieu", "2", "1", "2"],
             ["2026-10-20", "Sophie", "Pierre", "2", "1", "2"], ["2026-10-20", "Sarah", "Sarah", "1", "1", "1"],
             ["2026-10-20", "Maddie", "", "1", "1", "1"]]
    funnel = [["Date", "Leads (M1)", "Qualifiés (M2)", "Actifs (M3)"], ["19/10/2026", "6", "1", "4"]]
    parcours = [["ID Discord", "Clipper", "Créatrice", "Quiz réussi", "Arrivée Discord", "Compte 1 remis", "Compte 1 créé", "Compte 2 remis",
                 "Compte 2 créé", "Compte 3 remis", "Compte 3 créé", "App remise", "Premier jour tenu", "Visites payées 7 j", "Jours", "Statut"],
                ["1", "Alvaro - Sophie", "Sophie", "12/10/2026", "12/10/2026", "12/10/2026", "", "", "", "", "", "", "", "", "", "compte 1 à créer"],
                ["2", "Benn - Sophie", "Sophie", "19/10/2026", "19/10/2026", "19/10/2026", "", "", "", "", "", "", "", "", "", "compte 1 à créer"],
                ["3", "Simon - sarah", "sarah", "24/07/2026", "", "26/09/2026", "29/9/2026", "", "", "", "", "", "", "", "", "3 comptes"]]
    return {"subs": subs, "clics": clics, "reels": reels, "funnel": funnel, "parcours": parcours}


def test_cinq_lignes():
    texte = rq.composer_cockpit(HIER, onglets(), effectif=26)
    lignes = texte.split("\n")
    assert lignes[0] == "📊 **Mardi 20/10**, la veille"
    assert lignes[1].startswith("💰 **40 subs · 198 €** (OF 150 $ · MYM 60 €) · 7 j : 280 subs (0 %), 1 386 €")
    assert lignes[2] == "🔗 **100 clics payés** · créatrices 60 % · clippers 40 % · 7 j : 100"
    assert lignes[3] == "🎬 **16 Reels sur 150** · créatrices 2 · Metricool 10 · clippers 4 (2 clippers sur 26 ont publié)"
    assert lignes[4] == "🧲 6 leads · 1 qualifié(s) le 19/10 · 2 bloqué(s) au compte 1 (le plus ancien : Alvaro, 9 j)"
    assert lignes[-1].startswith("👉 Le détail : https://claude.ai/artifact/")


def test_hier_pas_saisi():
    o = onglets()
    o["subs"] = [l if not (l[0] == "2026-10-20") else l[:6] + ["non"] for l in o["subs"]]
    texte = rq.composer_cockpit(HIER, o)
    assert "💰 **Subs d'hier pas encore saisis** · 7 j :" in texte
    assert "Non saisi hier" not in texte


def test_une_creatrice_pas_saisie():
    texte = rq.composer_cockpit(HIER, onglets(saisi="non"))
    assert "⚠️ Non saisi hier : Sophie (Rianah)" in texte


def test_repli_ancien_format(monkeypatch):
    async def vide():
        return {}
    monkeypatch.setattr(rq, "lire_pilotage", vide)
    appels = []

    async def data_gm(_j):
        appels.append("data_gm")
        return {}
    monkeypatch.setattr(rq, "data_gm", data_gm)

    async def metricool(_h):
        return {}
    monkeypatch.setattr(rq, "metricool", metricool)
    rq.configurer({"heure_paris": lambda: __import__("datetime").datetime(2026, 10, 21, 13), "groupes": lambda: {}, "exclus": lambda: []})
    texte = asyncio.run(rq.executer())
    assert "la veille en 8 lignes" in texte and appels == ["data_gm"]
