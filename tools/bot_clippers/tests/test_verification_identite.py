"""14/10 : le code « confirmer votre identité / vérifier votre adresse e-mail » (déblocage d'un compte) est donné au clipper ;
tout mail qui parle aussi d'un changement sensible (mot de passe, ajout ou changement d'adresse, Espace Comptes, 2FA,
suppression) reste gardé. Mails inventés, construits sur le modèle du vrai mail Instagram du 14/10."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault("DONNEES_DIR", tempfile.mkdtemp())
os.environ["CODES_SECURITES"] = "1"
os.environ.pop("CODES_VERIFICATION", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import codes_2fa as C  # noqa: E402

DE = "Instagram <security@mail.instagram.com>"
PIED = ("\n\nMerci,\n\nL'équipe Instagram\n\nfrom\nMeta\n© Instagram. Meta Platforms, Inc., 1601 Willow Road, Menlo Park, CA 94025\n"
        "Ce message a été envoyé à alias@exemple.invalid et était destiné à compte.exemple.")
VRAI = ("Votre code de confirmation d'adresse e-mail\n\nHi,\n\nPour confirmer votre identité sur Instagram, nous devons vérifier "
        "votre adresse e-mail.\n\nCe code ne peut être utilisé qu'une fois. Si vous n'avez pas demandé de code, veuillez ignorer "
        "cet e-mail. Ne partagez jamais ce code.\n\nVotre code de confirmation d'adresse e-mail\n\n583673\n\ncompte.exemple" + PIED)


def classer(sujet, corps):
    return C.classer(DE, sujet, corps, [corps])


class VerificationIdentiteTests(unittest.TestCase):
    def test_vrai_mail_de_deblocage_donne(self):
        for sujet in ("Votre code de confirmation d'adresse e-mail", "583673 est votre code de confirmation",
                      "Vérifiez votre adresse e-mail"):
            r = classer(sujet, VRAI)
            self.assertEqual((r["decision"], r["type"], r["code"]), ("donner", "verification", "583673"), (sujet, r))

    def test_version_anglaise_donnee(self):
        corps = ("Hi,\n\nTo confirm your identity on Instagram, we need to verify your email address.\n\nThis code can only be "
                 "used once. If you didn't request this code, you can ignore this email.\n\nYour email confirmation code\n\n"
                 "481920" + "\n\nThanks,\nThe Instagram team\n© Instagram. Meta Platforms, Inc.")
        r = classer("Your email confirmation code", corps)
        self.assertEqual((r["decision"], r["type"]), ("donner", "verification"), r)

    def test_changements_sensibles_restent_gardes(self):
        dangereux = {
            "ajout d'adresse": "Pour confirmer votre identité, saisissez ce code pour ajouter cette nouvelle adresse e-mail à votre compte : 123456",
            "changement de mot de passe": "Pour confirmer votre identité avant de changer votre mot de passe, utilisez ce code : 123456",
            "réinitialisation": "Pour confirmer votre identité, utilisez ce code pour réinitialiser votre mot de passe : 123456",
            "Espace Comptes": "Pour confirmer votre identité dans l'Espace Comptes, utilisez ce code : 123456",
            "2FA": "To confirm your identity and turn off two-factor authentication, use this code: 123456",
            "suppression": "Pour confirmer votre identité avant de supprimer votre compte, utilisez ce code : 123456",
        }
        for nom, phrase in dangereux.items():
            r = classer("Votre code Instagram", "Hi,\n\n" + phrase + PIED)
            self.assertEqual(r["decision"], "garder", (nom, r))

    def test_interrupteur(self):
        self.assertTrue(C.CODES_VERIFICATION)
        self.assertIn("verification", C.QUOI)


if __name__ == "__main__":
    unittest.main()
