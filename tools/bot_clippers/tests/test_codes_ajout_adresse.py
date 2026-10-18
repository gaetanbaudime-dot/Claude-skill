"""18/10 (Pierre ne reçoit pas son code) : le code « ajout d'adresse » envoyé par Instagram à l'inscription est donné au clipper
de l'adresse quand son compte n'est pas encore créé ; jamais sur un compte vivant, jamais avec mot de passe ou téléphone."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_codes_reliable import load_codes  # noqa: E402

DE = "Instagram <security@mail.instagram.com>"
SUJET = "Votre code Instagram est le 482913"
CORPS = "Code pour votre nouvelle adresse e-mail : 482913."     # une NOUVELLE adresse : un changement


class AjoutAdresseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()

    def info(self, corps=CORPS, de=DE):
        i = self.c.classer(de, SUJET, corps)
        return dict(i, alias="a@icloud.com")

    def test_simple_mention_de_l_adresse_donnee(self):
        # 18/10, 13 h 52 (Gaëtan : « tous les codes SAUF changer… ») : citer l'adresse n'est pas la changer
        i = dict(self.c.classer(DE, SUJET, "Voici votre code pour votre adresse e-mail sur Instagram : 482913."), alias="a@icloud.com")
        self.c._deps.pop("compte_a_creer", None)
        self.assertEqual(self.c.promouvoir_creation(i)["decision"], "donner")

    def test_garde_sans_contexte(self):
        i = self.info()
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

    def test_code_meta_inscription(self):
        # 18/10 (Diamondra) : « Authenticate your profile » envoyé par Meta pendant la création du compte 1
        i = dict(self.c.classer("Meta <security@facebookmail.com>", "Authenticate your profile",
                                "Use this code to authenticate your profile: 482913."), alias="a@icloud.com")
        self.assertEqual(i["decision"], "garder")
        self.c._deps["compte_a_creer"] = lambda alias: True
        try:
            r = self.c.promouvoir_creation(i)
        finally:
            self.c._deps.pop("compte_a_creer", None)
        self.assertEqual((r["decision"], r["code"]), ("donner", "482913"))

    def test_code_meta_avec_mot_de_passe_garde(self):
        i = dict(self.c.classer("Meta <security@facebookmail.com>", "Authenticate your profile",
                                "Use this code to reset your password: 482913."), alias="a@icloud.com")
        self.c._deps["compte_a_creer"] = lambda alias: True
        try:
            self.assertNotEqual(self.c.promouvoir_creation(i)["decision"], "donner")
        finally:
            self.c._deps.pop("compte_a_creer", None)

    def test_jamais_hors_instagram(self):
        i = self.info(de="Inconnu <fraude@example.net>")
        self.assertFalse(i.get("ajout_adresse"))


if __name__ == "__main__":
    unittest.main()


class InscriptionTests(unittest.TestCase):
    """18/10 (Gaëtan : « Ceux-là tu peux renvoyer sans même ouvrir le mail ») : les modèles d'inscription d'Instagram."""
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()

    def test_inscription_francaise(self):
        r = self.c.classer("Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>", "Votre code Instagram est le 414503",
                           "Bonjour, Une personne a tenté de créer un compte an Instagram en utilisant l’adresse courriel suivante : "
                           "x@icloud.com. S’il s’agissait de vous, veuillez entrer ce code de confirmation dans l’application : 414503")
        self.assertEqual((r["decision"], r["type"], r["code"]), ("donner", "creation", "414503"))

    def test_inscription_anglaise(self):
        r = self.c.classer("Instagram <no-reply@mail.instagram.com>", "514445 is your Instagram code",
                           "Hi, Someone tried to sign up for an Instagram account with x@icloud.com. If it was you, enter this "
                           "confirmation code in the app: 514445")
        self.assertEqual((r["decision"], r["type"]), ("donner", "creation"))

    def test_modifier_les_reglages_reste_garde(self):
        r = self.c.classer("Meta <security@facebookmail.com>", "Authenticate your profile",
                           "Hi sophiepartenvan, Someone tried to modify settings on your account. Use this code to authenticate "
                           "your profile: 482913")
        self.assertNotEqual(r["decision"], "donner")
        self.c._deps["compte_a_creer"] = lambda alias: True
        try:
            self.assertNotEqual(self.c.promouvoir_creation(dict(r, alias="a@icloud.com"))["decision"], "donner")
        finally:
            self.c._deps.pop("compte_a_creer", None)

    def test_inscription_avec_mot_de_passe_garde(self):
        r = self.c.classer("Instagram <no-reply@mail.instagram.com>", "514445 is your Instagram code",
                           "Someone tried to sign up for Instagram. Use 514445 to reset your password.")
        self.assertNotEqual(r["decision"], "donner")


class ToutSaufChangementTests(unittest.TestCase):
    """18/10, 13 h 52 (Gaëtan : « Donne tous les codes SAUF changer les informations, mots de passe et mail ») ."""
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()

    def donne(self, de, sujet, corps):
        r = self.c.classer(de, sujet, corps)
        return self.c.promouvoir_creation(dict(r, alias="a@icloud.com"))["decision"] == "donner" or r["decision"] == "donner"

    def test_connexion_meta_donnee_meme_compte_cree(self):
        self.c._deps.pop("compte_a_creer", None)
        self.assertTrue(self.donne("Meta <security@facebookmail.com>", "Authenticate your profile",
                                   "Hi, use the following code to confirm your identity: 482913"))

    def test_changements_jamais(self):
        self.c._deps["compte_a_creer"] = lambda alias: False
        try:
            for corps in ("Someone tried to modify settings on your account. Code: 482913",
                          "Enter 482913 to change the email address on your account.",
                          "Use 482913 to reset your password.",
                          "Use 482913 to add a new email to your account."):
                self.assertFalse(self.donne("Instagram <security@mail.instagram.com>", "482913 is your Instagram code", corps), corps)
        finally:
            self.c._deps.pop("compte_a_creer", None)

    def test_fenetre_vingt_minutes(self):
        self.assertEqual(self.c.FRAIS_MIN, 20)
