"""18/10 (semaines 2-3 du plan) : relance H+24 du quiz réussi sans Discord (35), table « Parcours » (16), classement par
équipe TL et 30 jours dans !mesclics (28)."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import relances  # noqa: E402
import table_parcours  # noqa: E402


class QuizSansDiscordTests(unittest.TestCase):
    def setUp(self):
        self.maintenant = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
        q = lambda h, ok=True: {"reussi": ok, "date": (self.maintenant - timedelta(hours=h)).isoformat()}  # noqa: E731
        self.pipe = {
            "candidatures_web": {"a": {"tel": "+261341111111", "quiz": q(30)},
                                 "b": {"tel": "+261342222222", "quiz": q(30)},
                                 "c": {"tel": "+261343333333", "quiz": q(5)},
                                 "d": {"tel": "+261344444444", "quiz": q(30, ok=False)}},
            "candidatures": {"+261341111111": {"prenom": "Aina", "pays": "Madagascar"},
                             "+261342222222": {"prenom": "Bema"}},
            "liaisons": {"99": {"tel": "+261342222222"}}}

    def test_seul_le_quiz_reussi_depuis_24h_hors_discord(self):
        liste = relances.quiz_sans_discord(self.pipe, {}, self.maintenant)
        self.assertEqual([x[1] for x in liste], ["Aina"])

    def test_une_seule_relance(self):
        etat = {"discord": {relances.cle_tel("+261341111111"): "2026-10-17T09:00:00+00:00"}}
        self.assertEqual(relances.quiz_sans_discord(self.pipe, etat, self.maintenant), [])

    def test_bloc_avec_lien_pre_rempli(self):
        relances._deps["lien_formation"] = lambda cid: f"https://exemple.test/formation?t={cid}"
        bloc = relances.bloc_quiz_sans_discord(relances.quiz_sans_discord(self.pipe, {}, self.maintenant))
        self.assertIn("Quiz réussi, pas encore sur Discord : 1", bloc)
        self.assertIn("wa.me/261341111111?text=", bloc)


class TableParcoursTests(unittest.TestCase):
    def test_ligne_avec_dates_et_jour_tenu(self):
        paris = timezone(timedelta(hours=2))
        parcours = {"1": {"prenom": "Julien", "creatrice": "Sarah",
                          "dates": {"1": "2026-10-12T08:00:00+00:00", "1_fait": "2026-10-13T08:00:00+00:00"}}}
        pipe = {"etats": {"1": {"etat": "valide", "date_quiz": "2026-10-11T08:00:00+00:00"}},
                "arrivees": {"1": {"date": "2026-10-11T10:00:00+00:00"}}}
        paie = {"liens": {"L": {"uid": "1"}}}
        payees = lambda p, uid, a, b: 6 if a == b == date(2026, 10, 15) else (12 if a != b else 0)  # noqa: E731
        t = table_parcours.lignes(parcours, pipe, {"1": {"creatrice": "Sarah"}}, paie, payees, {"1": "Julien - Sarah"},
                                  date(2026, 10, 18), paris)
        self.assertEqual(t[0], table_parcours.ENTETE)
        ligne = dict(zip(t[0], t[1]))
        self.assertEqual(ligne["ID Discord"], "'1")
        self.assertEqual(ligne["Quiz réussi"], "11/10/2026")
        self.assertEqual(ligne["Compte 1 créé"], "13/10/2026")
        self.assertEqual(ligne["Premier jour tenu"], "15/10/2026")
        self.assertEqual(ligne["Jours quiz → compte 1 créé"], 2)
        self.assertEqual(ligne["Statut"], "compte 1 créé")

    def test_acces_en_attente_dans_le_statut(self):
        t = table_parcours.lignes({"2": {"creatrice": "Sarah", "acces_en_attente": "x",
                                         "dates": {"1": "2026-10-16T08:00:00+00:00"}}},
                                  {}, {}, {}, None, {}, date(2026, 10, 18), timezone.utc)
        self.assertEqual(t[1][-1], "compte 1 à créer (accès en attente)")


class ClassementEquipesTests(unittest.TestCase):
    def test_equipes_classees(self):
        import paie_clics
        hier = date(2026, 10, 18)
        d = {"liens": {"a": {"uid": "1"}, "b": {"uid": "2"}, "c": {"uid": "3"}}}
        valeurs = {"a": 100, "b": 50, "c": 400}
        ancien = paie_clics.somme
        paie_clics.somme = lambda d_, lids, debut, fin: {"payes": sum(valeurs[l] for l in lids)}
        try:
            texte = paie_clics.texte_classement(d, lambda u: f"C{u}", hier,
                                                equipe_de=lambda u: {"1": "Yves", "2": "Yves", "3": "Clarisse"}.get(u))
        finally:
            paie_clics.somme = ancien
        self.assertIn("Équipes de la semaine", texte)
        self.assertLess(texte.index("Équipe Clarisse"), texte.index("Équipe Yves"))
        self.assertIn("150 visites · 2 clipper(s)", texte.replace(" ", " ").replace("\xa0", " "))


if __name__ == "__main__":
    unittest.main()
