"""French Instagram identity confirmation classification regression cases."""
import unittest
from test_codes_reliable import load_codes

class FrenchIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=load_codes()
        cls.c.SECURITES=True
        cls.c.CODES_VERIFICATION=True

    def test_real_verification_with_footer(self):
        body=("Hi, Pour confirmer votre identité sur Instagram, nous devons vérifier "
              "votre adresse e-mail. Ce code ne peut être utilisé qu’une fois. "
              "Votre code de confirmation d’adresse e-mail 123456 "
              "Merci, L'équipe Instagram. Facebook Meta Platforms.")
        r=self.c.classer("Instagram <security@mail.instagram.com>",
                        "Votre code de confirmation d’adresse e-mail",body,[body])
        self.assertEqual((r["decision"],r["type"]),("donner","verification"))

    def test_account_change_instruction_refused(self):
        body=("Pour confirmer votre identité sur Instagram, nous devons vérifier "
              "votre adresse e-mail. Modifiez l’adresse e-mail de votre compte "
              "avec ce code 123456.")
        r=self.c.classer("Instagram <security@mail.instagram.com>",
                        "Votre code de confirmation d’adresse e-mail",body,[body])
        self.assertNotEqual(r["decision"],"donner")

    def test_fake_sender_refused(self):
        body=("Pour confirmer votre identité sur Instagram, nous devons vérifier "
              "votre adresse e-mail. Votre code de confirmation 123456")
        r=self.c.classer("Instagram <fraud@example.net>",
                         "Votre code de confirmation d’adresse e-mail",body,[body])
        self.assertNotEqual(r["decision"],"donner")

if __name__=="__main__":
    unittest.main()
