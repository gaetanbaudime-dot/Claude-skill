"""26/10 (Gaëtan, axe 3 : « Garde les 48 h pour les comptes 1 → 2 → 3. Mais le lien ne part qu'avec 6 Reels vérifiés sur les
comptes 1 et 2 ») : le compte 3 part à 48 h, le lien attend LIEN_REELS_MIN Reels vérifiés, puis part dans son message au passage
horaire. Cas fictifs, sans réseau ni Discord."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import parcours  # noqa: E402
import places  # noqa: E402


class LienRetenuTests(unittest.TestCase):
    def setUp(self):
        self.fiche = {"etape": 3, "ordre": "prive3", "dates": {"1_fait": "2026-10-20T10:00:00+00:00", "2_fait": "2026-10-22T10:00:00+00:00"}}
        parcours.LIEN_REELS_MIN = 6

    def retenu(self, reels_par_compte, lien="", simple=True):
        with patch.object(parcours, "reels_verifies", side_effect=lambda uid, f, k: reels_par_compte.get(k, 0)), \
                patch.object(parcours, "_onb", return_value={"lien": lien}), \
                patch.object(parcours, "simple", return_value=simple):
            return parcours.lien_retenu("1", self.fiche)

    def test_il_manque_des_reels(self):
        self.assertEqual(4, self.retenu({1: 2, 2: 0}))
        self.assertEqual(1, self.retenu({1: 3, 2: 2}))

    def test_objectif_tenu_sur_les_deux_comptes(self):
        self.assertEqual(0, self.retenu({1: 4, 2: 2}))
        self.assertEqual(0, self.retenu({1: 6, 2: 0}), "6 Reels à eux deux, peu importe la répartition")

    def test_jamais_retenu_hors_regle(self):
        self.assertEqual(0, self.retenu({1: 0, 2: 0}, lien="https://example.invalid/3"), "lien déjà là")
        self.assertEqual(0, self.retenu({1: 0, 2: 0}, simple=False), "ancien parcours")
        parcours.LIEN_REELS_MIN = 0
        self.assertEqual(0, self.retenu({1: 0, 2: 0}), "règle coupée")


class LivraisonTests(unittest.TestCase):
    def setUp(self):
        parcours.LIEN_REELS_MIN = 6
        self.fiches = {"1": {"etape": 3, "ordre": "prive3", "salon_id": "10", "prenom": "Fictif",
                             "dates": {"1_fait": "x", "2_fait": "y", "3": "z"},
                             "lien_attendu": {"objectif": 6, "depuis": "2026-10-26T08:00:00+00:00"}}}
        self.onb = {"1": {"comptes": ["c.un", "c.deux", "c.prive"], "lien": ""}}
        self.salon = SimpleNamespace(id=10, send=AsyncMock(), guild=None)
        self.client = SimpleNamespace(get_channel=lambda i: self.salon if i == 10 else None)
        self.ancien = dict(parcours._deps)

        async def attribuer(membre, raison=""):
            self.onb["1"]["lien"] = "https://example.invalid/3"
            self.onb["1"]["liens_prets"] = True
        self.attribuer = AsyncMock(side_effect=attribuer)
        parcours._deps.update(membre_par_id=lambda uid: SimpleNamespace(id=int(uid), mention="@f"), attribuer_lien=self.attribuer)

    def tearDown(self):
        parcours._deps.clear()
        parcours._deps.update(self.ancien)

    def lancer(self, reels):
        with patch.object(parcours, "_lire", side_effect=lambda: self.fiches), \
                patch.object(parcours, "_ecrire", side_effect=lambda d: self.fiches.update(d)), \
                patch.object(parcours, "_onb", side_effect=lambda uid: self.onb.get(str(uid), {})), \
                patch.object(parcours, "reels_verifies", side_effect=lambda uid, f, k: reels.get(k, 0)), \
                patch.object(parcours, "_comptes_ordonnes", side_effect=lambda uid, onb=None, fiche_p=None: self.onb["1"]["comptes"]), \
                patch.object(parcours, "envoyer_etape", AsyncMock(return_value=True)) as etape7:
            faits = asyncio.run(parcours.livrer_liens_attendus(self.client))
        return faits, etape7

    def test_pas_assez_de_reels_rien_ne_part(self):
        faits, _ = self.lancer({1: 3, 2: 2})
        self.assertEqual([], faits)
        self.attribuer.assert_not_awaited()
        self.assertIn("lien_attendu", self.fiches["1"])

    def test_objectif_tenu_le_lien_est_cree_et_donne(self):
        faits, etape7 = self.lancer({1: 4, 2: 2})
        self.assertEqual([("1", "lien", 3)], faits)
        self.attribuer.assert_awaited_once()
        texte = self.salon.send.await_args.args[0]
        self.assertIn("https://example.invalid/3", texte)
        self.assertIn("6 Reels publiés", texte)
        self.assertIn("`c.prive`", texte)
        self.assertNotIn("lien_attendu", self.fiches["1"])
        self.assertEqual("https://example.invalid/3", self.fiches["1"]["lien_profil"])
        etape7.assert_not_awaited()                                     # profil du privé pas encore fait : la routine attend le ✅

    def test_profil_deja_fait_la_routine_part_avec_le_lien(self):
        self.fiches["1"]["dates"]["3_fait"] = "w"
        _, etape7 = self.lancer({1: 6, 2: 0})
        etape7.assert_awaited_once()
        self.assertEqual(7, etape7.await_args.args[2])

    def test_forfait_plein_on_reessaie_plus_tard(self):
        self.attribuer.side_effect = RuntimeError("forfait GAML plein")
        faits, _ = self.lancer({1: 6, 2: 1})
        self.assertEqual([], faits)
        self.assertIn("lien_attendu", self.fiches["1"])


class DigestTests(unittest.TestCase):
    def test_lien_attendu_n_est_pas_un_compte_prive_sans_lien(self):
        fiches = {"1": {"etape": 3, "prenom": "Fictif", "dates": {"3": "x"}, "lien_attendu": {"objectif": 6}},
                  "2": {"etape": 3, "prenom": "Autre", "dates": {"3": "x"}}}
        ancien = dict(parcours._deps)
        parcours._deps.update(FICHIER_EQUIPES="eq", lire_json=lambda f, d: {"1": {}, "2": {}})
        try:
            with patch.object(parcours, "_lire", return_value=fiches), \
                    patch.object(places.onboarding, "_lire_etat", return_value={"clippers": {}}), \
                    patch.object(places.paie_clics, "actif", return_value=True), \
                    patch.object(places.paie_clics, "_lire", return_value={"liens": {}}):
                self.assertEqual([("2", "Autre")], places.sans_lien())
        finally:
            parcours._deps.clear()
            parcours._deps.update(ancien)


class TexteTests(unittest.TestCase):
    def test_ligne_du_compte_3_sans_lien(self):
        t = parcours.LIGNE_LIEN_ATTENDU.format(objectif=6, vus=2)
        self.assertIn("6 Reels publiés", t)
        self.assertIn("Tu en as 2", t)


if __name__ == "__main__":
    unittest.main()


class ConnaissancesTests(unittest.TestCase):
    def test_base_et_assistant_disent_la_regle(self):
        kb = (ROOT / "connaissances.md").read_text(encoding="utf-8")
        self.assertIn("6 Reels publiés à eux deux", kb)
        self.assertIn("Pourquoi je n'ai pas encore mon lien ?", kb)
        self.assertNotIn("Le bot te donne ton lien en même temps que lui", kb)
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("32 bis. Le lien (26/10", src)
        self.assertIn("6 Reels publiés à eux deux", parcours.regle_comptes())
