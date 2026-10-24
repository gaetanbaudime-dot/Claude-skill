"""18/10 (actions 16-17) : M1 · M2 · M3 jour par jour, définitions gelées. Cas fictifs."""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import funnel_quotidien as f  # noqa: E402

J = date(2026, 10, 17)
PIPE = {
    "arrivees": {"1": {"date": "2026-10-17T10:00:00+00:00"},    # quiz la veille : qualifié
                 "2": {"date": "2026-10-17T11:00:00+00:00"},    # quiz 3 jours avant : pas qualifié (pas sous 24 h)
                 "3": {"date": "2026-10-17T12:00:00+00:00"},    # quiz raté
                 "4": {"date": "2026-10-16T12:00:00+00:00"}},   # arrivé un autre jour
    "etats": {"1": {"etat": "valide", "date_quiz": "2026-10-16T20:00:00+00:00"},
              "2": {"etat": "valide", "date_quiz": "2026-10-14T20:00:00+00:00"},
              "3": {"etat": "quiz_rate", "date_quiz": "2026-10-17T09:00:00+00:00"},
              "4": {"etat": "valide", "date_quiz": "2026-10-16T09:00:00+00:00"}}}


class FunnelTests(unittest.TestCase):
    def test_m2_quiz_et_discord_sous_24h(self):
        self.assertEqual(f.qualifies(PIPE, J, timezone.utc), ["1"])

    def test_m3_jour_tenu_a_5(self):
        paie = {"liens": {"a": {"uid": "1"}, "b": {"uid": "2"}, "c": {"uid": "9"}, "d": {"uid": "3", "archive": True}}}
        visites = {"1": 5, "2": 4, "9": 40, "3": 99}
        self.assertEqual(f.actifs(paie, J, lambda d, uid, a, b: visites[uid], exclus={"9"}), ["1"])

    def test_textes(self):
        lignes = f.serie([J, date(2026, 10, 16)], lambda j: 10, lambda j: 3, lambda j: 2)
        self.assertIn("M1 **10** · M2 **3** · M3 **2**", f.texte(lignes))
        self.assertIn("M2/M1 30 %", f.texte(lignes))
        self.assertIn("2 clipper(s) actif(s) hier", f.ligne_digest(lignes))          # 21/10 : leads et qualifiés sont au-dessus
        self.assertIn("moyenne 7 j : 10,0 lead(s), 3,0 qualifié(s), 2,0 actif(s) par jour", f.ligne_digest(lignes))
        self.assertEqual(f.lignes_feuille(lignes)[1][0], "16/10/2026")


class NouvellesPersonnesTests(unittest.TestCase):
    """24/10 : M1 = une personne une fois, le jour de sa toute première candidature ; tests exclus. Cas fictifs."""
    J1, J2, J3 = datetime(2026, 9, 28, 10), datetime(2026, 9, 29, 11), datetime(2026, 9, 30, 9)

    def test_tests_exclus_quelle_que_soit_la_casse(self):
        envois = [{"date": self.J2, "prenom": p, "telegram": "test", "pays": "France"} for p in ("test", "TEst", "Test", "Test Claude")]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {})
        self.assertFalse(f.est_test("Testa"))

    def test_meme_envoi_classeur_et_pipeline_compte_une_fois(self):
        # le classeur n'a pas de numéro lisible, le pipeline l'a : le pseudo Telegram les relie
        envois = [{"date": self.J2, "tel": "majeur, iPhone", "telegram": "@candidat_mg1", "prenom": "Lova", "pays": "Madagascar"},
                  {"date": self.J2, "tel": "+261 34 11 22 33 44", "telegram": "@candidat_mg1", "prenom": "Lova", "pays": "Madagascar"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J2.date(): 1})

    def test_recandidature_comptee_au_premier_jour(self):
        envois = [{"date": self.J1, "tel": "", "telegram": "Rado Fidy", "prenom": "Fidy"},
                  {"date": self.J1, "tel": "+261 34 99 88 77 66", "telegram": "Rado Fidy", "prenom": "Fidy"},
                  {"date": self.J3, "tel": "+261 34 99 88 77 66", "telegram": "Fidy Rado", "prenom": "Fidy"},
                  {"date": self.J3, "tel": "", "telegram": "Fidy Rado", "prenom": "Fidy"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J1.date(): 1})

    def test_doublons_sans_numero_ni_pseudo_par_prenom_et_pays(self):
        envois = [{"date": self.J1, "prenom": "Noël", "telegram": "même numéro", "pays": "France"},
                  {"date": self.J1, "prenom": "Noel", "telegram": "meme numero", "pays": "France"},
                  {"date": self.J1, "prenom": "Noël", "pays": "Bénin"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J1.date(): 2})

    def test_pseudo_qui_est_un_numero_vaut_numero(self):
        envois = [{"date": self.J1, "telegram": "5612345678", "prenom": "Max"},
                  {"date": self.J2, "tel": "+229 56 12 34 56 78", "prenom": "Max"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J1.date(): 1})

    def test_personnes_differentes_et_lignes_vides(self):
        envois = [{"date": self.J2, "tel": "+33 6 11 11 11 11", "prenom": "A"},
                  {"date": self.J2, "tel": "+33 6 22 22 22 22", "prenom": "A"},      # même prénom, autre numéro
                  {"date": self.J2},                                              # ligne vide
                  {"date": None, "tel": "+33 6 33 33 33 33", "prenom": "C"}]      # date illisible
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J2.date(): 2})


class PseudosQuiNeReliePersonneTests(unittest.TestCase):
    J1, J2 = datetime(2026, 9, 28, 10), datetime(2026, 10, 17, 11)

    def test_pseudo_du_staff(self):
        envois = [{"date": self.J1, "telegram": "Gaetan_ofm", "prenom": "Gaetan"},                 # test du staff : écarté
                  {"date": self.J2, "tel": "+261 34 00 00 00 01", "telegram": "@gaetan_ofm", "prenom": "Antonio"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J2.date(): 1})

    def test_pseudo_porte_par_deux_numeros(self):
        envois = [{"date": self.J1, "tel": "+229 01 11 11 11 11", "telegram": "@famille", "prenom": "A"},
                  {"date": self.J2, "tel": "+229 01 22 22 22 22", "telegram": "@famille", "prenom": "B"}]
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {self.J1.date(): 1, self.J2.date(): 1})


class EnvoisCandidaturesTests(unittest.TestCase):
    """La collecte des envois dans bot_discord (extraite de l'AST, sans lancer le bot)."""

    def setUp(self):
        import ast
        import types
        from datetime import timedelta
        src = (Path(__file__).resolve().parents[1] / "bot_discord.py").read_text(encoding="utf-8")
        arbre = ast.parse(src)
        fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "envois_candidatures")
        ns = {"datetime": datetime, "timezone": timezone, "timedelta": timedelta,
              "relances": types.SimpleNamespace(tel_exclu=lambda t: "0600000000" in str(t))}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "bot_discord.py", "exec"), ns)
        self.envois = ns["envois_candidatures"]

    def test_classeur_fiche_historique_web_et_staff(self):
        lignes = [{"date": datetime(2026, 9, 29, 11, 0), "tel": "", "telegram": "@alexis_x1", "prenom": "Alexis", "pays": "Madagascar"},
                  {"date": datetime(2026, 9, 29, 12, 0), "tel": "0600000000", "prenom": "Staff"}]
        pipe = {"candidatures": {"+261340000001": {"date": "2026-09-30T06:00:00+00:00", "pseudo": "@alexis_x1", "prenom": "Alexis"}},
                "candidatures_contact_historique": {"+261340000001": [{"date": "2026-09-29T08:00:00+00:00", "pseudo": "@alexis_x1"}]},
                "candidatures_web": {"c1": {"tel": "+261340000001", "date": "2026-09-29T08:00:00+00:00",
                                            "dossier": {"pseudo": "@alexis_x1", "prenom": "Alexis"}}}}
        envois = self.envois(lignes, pipe)
        self.assertEqual(len(envois), 4)                                     # le staff est écarté
        self.assertEqual(envois[1]["date"], datetime(2026, 9, 30, 8, 0))     # UTC ramené à Paris (heure d'été)
        self.assertEqual(f.nouvelles_personnes_par_jour(envois), {date(2026, 9, 29): 1})


if __name__ == "__main__":
    unittest.main()
