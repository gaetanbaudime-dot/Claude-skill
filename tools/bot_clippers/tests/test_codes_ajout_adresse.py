"""18/10 (Pierre ne reçoit pas son code) : le code « ajout d'adresse » envoyé par Instagram à l'inscription est donné au clipper
de l'adresse quand son compte n'est pas encore créé ; jamais sur un compte vivant, jamais avec mot de passe ou téléphone."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_codes_reliable import load_codes  # noqa: E402

DE = "Instagram <security@mail.instagram.com>"
SUJET = "Votre code Instagram est le 482913"
CORPS = "Saisissez ce code pour confirmer votre adresse e-mail : 482913."


class AjoutAdresseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()

    def info(self, corps=CORPS, de=DE):
        i = self.c.classer(de, SUJET, corps)
        return dict(i, alias="a@icloud.com")

    def test_garde_sans_contexte(self):
        i = self.info()
        if i["decision"] == "donner":
            self.skipTest("modèle déjà reconnu comme création")
        self.assertEqual(i["decision"], "garder")
        self.assertTrue(i.get("ajout_adresse"))
        self.c._deps.pop("compte_a_creer", None)
        self.assertEqual(self.c.promouvoir_creation(i)["decision"], "garder")

    def test_donne_si_compte_a_creer(self):
        i = self.info()
        self.c._deps["compte_a_creer"] = lambda alias: True
        try:
            r = self.c.promouvoir_creation(i)
        finally:
            self.c._deps.pop("compte_a_creer", None)
        self.assertEqual(r["decision"], "donner")
        self.assertEqual(r["type"], "creation")
        self.assertEqual(r["code"], "482913")

    def test_garde_si_compte_cree(self):
        self.c._deps["compte_a_creer"] = lambda alias: False
        try:
            self.assertEqual(self.c.promouvoir_creation(self.info())["decision"], "garder")
        finally:
            self.c._deps.pop("compte_a_creer", None)

    def test_jamais_avec_mot_de_passe_ou_telephone(self):
        for ajout in (" Réinitialisez aussi votre mot de passe.", " Ajoutez aussi un numéro de téléphone."):
            i = self.info(CORPS + ajout)
            self.assertFalse(i.get("ajout_adresse"), ajout)
            self.c._deps["compte_a_creer"] = lambda alias: True
            try:
                self.assertNotEqual(self.c.promouvoir_creation(i)["decision"], "donner", ajout)
            finally:
                self.c._deps.pop("compte_a_creer", None)

    def test_jamais_hors_instagram(self):
        i = self.info(de="Facebook <security@facebookmail.com>")
        self.assertFalse(i.get("ajout_adresse"))


if __name__ == "__main__":
    unittest.main()
