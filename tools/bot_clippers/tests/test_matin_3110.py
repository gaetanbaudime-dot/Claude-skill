"""31/10 (Gaëtan : « Met en place toutes les recommandations de l'audit du process » ; « Liste du matin, tu valides ») : les 3 chiffres
du matin, la liste « 0 Reel depuis 7 jours », la formation → quiz, l'onglet Parcours qui compte les comptes vus sur Instagram.
Cas fictifs, sans réseau."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import funnel_quotidien
import pilotage
import sortie_auto
import table_parcours

REELS = [["2026-10-30", "Chloé", "Fictif", "10", "1", "1"],
         ["2026-10-30", "Chloé", "Rianah (Metricool)", "2", "1", "1"],
         ["2026-10-30", "Chloé", "Rianah Clipping Chloé", "1", "1", "1"],
         ["2026-10-30", "Sophie", "Sophie", "3", "1", "1"],
         ["2026-10-30", "Jade", "", "1", "1", "1"],
         ["2026-10-30", "Sophie", "Tl Fictif", "3", "1", "1"],
         ["2026-10-30", "Sophie", "Zéro Fictif", "0", "0", "0"],
         ["2026-10-29", "Chloé", "Fictif", "7", "1", "1"]]
CLICS = [["2026-10-30", "Chloé", "Horizontal", "Clipper", "Fictif", "120", "130", "1", "0"],
         ["2026-10-30", "Sophie", "Horizontal", "Clipper", "Tl Fictif", "30", "31", "2", "1"],
         ["2026-10-30", "Sophie", "Horizontal", "Metricool", "x", "500", "500", "1", "0"],
         ["2026-10-29", "Chloé", "Horizontal", "Clipper", "Fictif", "99", "99", "1", "0"]]


class TroisChiffresTests(unittest.TestCase):
    def test_gerants(self):
        self.assertTrue(pilotage.gerant_clipper("Fictif", "Chloé"))
        for g, cr in (("Rianah (Metricool)", "Chloé"), ("Rianah Clipping Sarah", "Sarah"), ("Chloe", "Chloé"), ("", "Jade")):
            self.assertFalse(pilotage.gerant_clipper(g, cr), g)

    def test_chiffres(self):
        c = pilotage.trois_chiffres(REELS, CLICS, "2026-10-30")
        self.assertEqual({"actifs": 2, "reels": 13, "moyenne": 1.0, "clics": 150, "liens_non_releves": 1}, c)
        self.assertEqual({}, pilotage.trois_chiffres(None, CLICS, "2026-10-30"))

    def test_ligne(self):
        with patch.dict(pilotage.dernier, {"reels": REELS, "clics": CLICS}, clear=True):
            ligne = pilotage.ligne_trois_chiffres("2026-10-30")
        self.assertTrue(ligne.startswith("📈 **Hier** : 2 clipper(s) actif(s) · 13 Reels clippers · 150 clics francophones (relevé partiel)"))
        self.assertIn("Moyenne des 7 jours d'avant : 1,0 Reels par jour · objectif 2 000 par jour", ligne)
        with patch.dict(pilotage.dernier, {}, clear=True):
            self.assertEqual("", pilotage.ligne_trois_chiffres("2026-10-30"))

    def test_le_dashboard_garde_ses_tables_pour_le_matin(self):
        source = Path(pilotage.__file__).read_text(encoding="utf-8")
        self.assertIn('dernier.update({"reels": pil.get("reels"), "clics": pil.get("clics")', source)


class SansReelTests(unittest.TestCase):
    REF = datetime(2026, 10, 20, tzinfo=timezone.utc)

    def test_qui_est_liste(self):
        silences = [("1", "Un", 12, 10, self.REF),     # listé
                    ("2", "Deux", 9, 2, self.REF),      # pas mesuré : jamais listé
                    ("3", "Trois", 6, 6, self.REF),     # moins de 7 jours
                    ("4", "Quatre", 8, 8, self.REF),    # parti du serveur
                    ("5", "Cinq", 30, 25, self.REF),    # ses liens ramènent des visites : il publie ailleurs
                    ("6", "Six", 7, 5, self.REF)]       # listé, juste à 7 jours
        out = sortie_auto.a_valider_sans_reel(silences, present=lambda u: u != "4", produit=lambda u: u == "5", jours=7, scans_min=5)
        self.assertEqual([("1", "Un", 12), ("6", "Six", 7)], out)
        self.assertEqual([], sortie_auto.a_valider_sans_reel(silences, present=lambda u: True, jours=0))

    def test_bloc(self):
        bloc = sortie_auto.bloc_sans_reel([("1", "Un", 12)])
        self.assertIn("<@1> (12 j)", bloc)
        self.assertIn("`!sortie @x raison` pour le sortir, `!note @x garde` pour le garder. Rien n'est fait sans toi.", bloc)
        self.assertEqual("", sortie_auto.bloc_sans_reel([]))

    def test_branche_au_point_du_matin_sans_sortie_automatique(self):
        source = Path(sortie_auto.__file__).with_name("bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("sans_reel_d = await sortie_auto.sans_reel_a_valider()", source)
        self.assertIn("a_agir = (bloques_d or sans_reel_d", source)
        self.assertIn("pilotage.ligne_trois_chiffres(hier.isoformat())", source)
        self.assertIn("funnel_quotidien.ligne_formation(c_f, 14)", source)
        mod = Path(sortie_auto.__file__).read_text(encoding="utf-8")
        debut = mod.index("async def sans_reel_a_valider")
        self.assertNotIn("sortir", mod[debut:mod.index("def bloc_sans_reel")].replace("à sortir", ""))


class FormationQuizTests(unittest.TestCase):
    def test_qui_decroche_ou(self):
        pipe = {"candidatures_web": {
                    "a": {"tel": "+33 6 00 00 00 01", "date": "2026-10-28T10:00:00+00:00"},                           # vidéo
                    "b": {"tel": "+33 6 00 00 00 02", "date": "2026-10-28T10:00:00+00:00"},                           # quiz ouvert
                    "c": {"tel": "+33 6 00 00 00 03", "date": "2026-10-29T10:00:00+00:00", "quiz": {"essais": 1}},   # envoyé, raté
                    "d": {"tel": "+33 6 00 00 00 04", "date": "2026-10-29T10:00:00+00:00",
                          "quiz": {"essais": 2, "reussi": True}},
                    "d2": {"tel": "06 00 00 00 04", "date": "2026-10-30T10:00:00+00:00"},                            # même personne
                    "vieux": {"tel": "+33 6 00 00 00 05", "date": "2026-09-01T10:00:00+00:00"},
                    "staff": {"tel": "+33 6 00 00 00 09", "date": "2026-10-29T10:00:00+00:00"}},
                "quiz_tentatives_web": {"c:b": {"id": "x"}}}
        c = funnel_quotidien.formation_quiz(pipe, date(2026, 10, 17), date(2026, 10, 30), timezone.utc,
                                            exclu=lambda tel: str(tel).endswith("09"))
        self.assertEqual({"formulaires": 4, "quiz_ouvert": 3, "quiz_envoye": 2, "reussi": 1}, c)
        ligne = funnel_quotidien.ligne_formation(c, 14)
        self.assertIn("4 formulaire(s) → 3 ont ouvert le quiz (75 %) → 2 l'ont envoyé (50 %) → 1 réussi(s)", ligne)
        self.assertIn("décroché sur la page de la vidéo (1)", ligne)
        self.assertEqual("", funnel_quotidien.ligne_formation({"formulaires": 0}, 14))


class ParcoursTests(unittest.TestCase):
    def test_compte_vu_sur_instagram_compte_comme_cree(self):
        f = {"creatrice": "Sophie", "prenom": "Fictive",
             "dates": {"1": "2026-10-25T10:00:00+00:00", "2": "2026-10-27T10:00:00+00:00"},
             "crees_ig": {"1": {"h": "un.fictif", "le": "2026-10-31T06:00:00+00:00"}}}
        table = table_parcours.lignes({"42": f}, {}, {}, {}, None, {}, date(2026, 10, 31), timezone.utc)
        ligne = dict(zip(table_parcours.ENTETE, table[1]))
        self.assertEqual("31/10/2026", ligne["Compte 1 créé"])
        self.assertEqual("compte 1 créé", ligne["Statut"])


if __name__ == "__main__":
    unittest.main()
