import unittest
from test_codes_reliable import load_codes

class VerificationEmailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()
        cls.c.SECURITES = True
        cls.c.CODES_VERIFICATION = True

    def check(self, body, subject="Votre code de confirmation d’adresse e-mail", sender="Instagram <security@mail.instagram.com>"):
        return self.c.classer(sender, subject, body, complets=[body])

    def test_existing_email_identity(self):
        body = ("Pour confirmer votre identité sur Instagram, nous devons vérifier votre adresse e-mail. "
                "Votre code de confirmation d’adresse e-mail 123456. "
                "Merci, l'équipe Instagram, from Meta, Facebook, Threads.")
        self.assertEqual(self.check(body)["decision"], "donner")

    def test_address_change_not_allowed(self):
        body = ("Pour confirmer votre identité sur Instagram, nous devons vérifier votre adresse e-mail. "
                "Vous avez demandé de changer votre adresse e-mail. Votre code : 123456.")
        self.assertNotEqual(self.check(body)["decision"], "donner")

    def test_unknown_sender_not_allowed(self):
        body = ("Pour confirmer votre identité sur Instagram, nous devons vérifier votre adresse e-mail. "
                "Votre code : 123456.")
        self.assertNotEqual(self.check(body, sender="Test <unknown@example.org>")["decision"], "donner")

if __name__ == "__main__":
    unittest.main()
