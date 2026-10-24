"""24/10 (Gaëtan : « le vertical s'arrête au 3 octobre ; prends GAML et va chercher les six derniers mois ») : historique des clics
relu jusqu'à 183 jours. Cas fictifs, sans réseau."""
import asyncio
import os
import sys
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard  # noqa: E402
import paie_clics as p  # noqa: E402

MAINTENANT = datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc)
# identifiants au format UUID version 7 : 01a0e5de-4079-… = créé le 28/09/2026, 019dc8ac-128b-… = le 26/04/2026
NEUF = "01a0e5de-4079-7617-8cf1-43d7d2941c3b"
ANCIEN = "019dc8ac-128b-7538-ab7c-bbc5c39f5693"


class CreeLeTests(unittest.TestCase):
    def test_uuid_v7(self):
        self.assertEqual(p.cree_le(NEUF), date(2026, 9, 28))
        self.assertEqual(p.cree_le(ANCIEN), date(2026, 4, 26))

    def test_autre_format(self):
        self.assertIsNone(p.cree_le("12345"))
        self.assertIsNone(p.cree_le("019dc8ac-128b-4538-ab7c-bbc5c39f5693"))   # version 4 : pas de date


class PlanTests(unittest.TestCase):
    def d(self):
        jours_lus = {f"2026-10-{j:02d}": {"payes": 1, "hors_robots": 1} for j in range(3, 23)}
        return {"liens": {NEUF: {"uid": "", "releve": True},                         # page de créatrice
                          ANCIEN: {"uid": "42", "depuis": "2026-10-05"},             # lien d'un clipper
                          "019dc8ac-128b-7538-ab7c-000000000000": {"uid": "", "supprime_gaml": "2026-10-10"}},
                "jours": {NEUF: dict(jours_lus), ANCIEN: dict(jours_lus)}}

    def test_du_plus_recent_au_plus_ancien_pages_des_creatrices_d_abord(self):
        plan = p.plan_historique(self.d(), MAINTENANT, jours=183)
        self.assertEqual(plan[:4], [(NEUF, date(2026, 10, 2)), (ANCIEN, date(2026, 10, 2)), (NEUF, date(2026, 10, 1)),
                                    (ANCIEN, date(2026, 10, 1))])
        self.assertNotIn("019dc8ac-128b-7538-ab7c-000000000000", {lid for lid, _ in plan})   # effacé de GAML : jamais

    def test_jamais_avant_la_creation_ni_au_dela_de_la_fenetre(self):
        plan = p.plan_historique(self.d(), MAINTENANT, jours=183)
        neuf = [j for lid, j in plan if lid == NEUF]
        self.assertEqual(min(neuf), date(2026, 9, 28))                   # créé le 28/09
        ancien = [j for lid, j in plan if lid == ANCIEN]
        self.assertEqual(min(ancien), date(2026, 4, 26))                 # fenêtre de 183 j : 24/04, créé le 26/04
        self.assertTrue(all(j <= date(2026, 10, 22) for _, j in plan))   # la veille et le jour en cours : pas ici

    def test_coupe(self):
        self.assertEqual(p.plan_historique(self.d(), MAINTENANT, jours=0), [])


class RattrapageTests(unittest.TestCase):
    def test_un_appel_par_jour_sans_visitors_et_plafond(self):
        d = {"liens": {NEUF: {"uid": "", "releve": True}}, "jours": {NEUF: {}}}
        vus = []

        async def faux_relever(d_, lid, j, maintenant, visiteurs):
            vus.append((lid, j, dict(visiteurs)))
            d_["jours"][lid][j.isoformat()] = {"payes": 3, "hors_robots": 4}
            return "ok"
        with patch.object(p, "relever_jour", faux_relever), patch.object(p, "RELEVE_PAUSE", 0), \
                patch.dict(p._deps, {"heure_paris": lambda: MAINTENANT}):
            n = asyncio.run(p.rattraper_historique(d, maximum=5))
        self.assertEqual(n, 5)
        self.assertEqual([j for _, j, _ in vus], [date(2026, 10, 22), date(2026, 10, 21), date(2026, 10, 20), date(2026, 10, 19),
                                                  date(2026, 10, 18)])
        self.assertTrue(all(v["coupe"] for _, _, v in vus))              # countries seul : un appel

    def test_arret_sur_erreur_globale(self):
        d = {"liens": {NEUF: {"uid": "", "releve": True}}, "jours": {NEUF: {}}}

        async def panne(*_a, **_k):
            return "global"
        with patch.object(p, "relever_jour", panne), patch.object(p, "RELEVE_PAUSE", 0), \
                patch.dict(p._deps, {"heure_paris": lambda: MAINTENANT}):
            self.assertEqual(asyncio.run(p.rattraper_historique(d, maximum=50)), 1)


class CompteDeCreatriceTests(unittest.TestCase):
    def test_note_compte_de_creatrice(self):
        for note in ("Rianah Metricool + Compte de Créatrice", "compte créatrice", "Compte de la créatrice"):
            self.assertTrue(dashboard._RE_COMPTE_CREATRICE.search(note), note)
        self.assertFalse(dashboard._RE_COMPTE_CREATRICE.search("Rianah Metricool Redirect YTB"))

    def test_six_mois_publies(self):
        if "PILOTAGE_JOURS" not in os.environ:
            self.assertEqual(dashboard.PILOTAGE_JOURS, 183)


if __name__ == "__main__":
    unittest.main()
