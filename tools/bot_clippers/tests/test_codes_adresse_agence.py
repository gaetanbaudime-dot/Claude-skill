"""24/10 (Pierre, compte 1) : « Confirmez votre adresse courriel » — Instagram demande de confirmer L'ADRESSE DE L'AGENCE que le
clipper vient de rattacher au compte. Le code est donné à son propriétaire, jamais si l'adresse confirmée n'est pas celle qui
reçoit le mail, jamais avec mot de passe, téléphone ou 2FA. Modèles synthétiques : aucun vrai mail, alias ni code."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
import unittest

from test_codes_reliable import load_codes

DE = "Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>"
SUJET = "Confirmez votre adresse courriel"
ALIAS = "alias.fictif@example.invalid"


def corps(adresse=ALIAS, ajout=""):
    return ("Facebook\n\nBonjour compte.fictif, Vous avez récemment ajouté " + adresse + " à votre profil Instagram.\n"
            "Veuillez confirmer cette adresse courriel afin que nous puissions mettre vos coordonnées à jour." + ajout +
            " Il vous sera peut-être demandé d’entrer ce code de confirmation :\n483921\n\nde\n© Instagram. Meta Platforms, Inc., "
            "1601 Willow Road, Menlo Park, CA 94025, États-Unis\nCe message a été envoyé à " + adresse + ".\n"
            "To help keep your profile secure, please don't forward this email.")


class AdresseAgenceTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 23, 10, 32, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now
        self.c.IMAP_USER = "boite@example.invalid"

    def mail(self, a=ALIAS, adresse_corps=ALIAS, ajout=""):
        m = EmailMessage()
        m["From"] = DE
        m["To"] = a
        m["Subject"] = SUJET
        m["Date"] = format_datetime(self.now)
        m["Message-ID"] = "<adresse-agence@example.invalid>"
        m["Authentication-Results"] = "mx.google.com; dkim=pass header.d=mail.instagram.com"
        m.set_content(corps(adresse_corps, ajout))
        return m

    def test_modele_reel_donne(self):
        i = self.c.classer(DE, SUJET, corps())
        self.assertEqual(("donner", "verification", "483921"), (i["decision"], i["type"], i["code"]))
        self.assertEqual(ALIAS, i["adresse_confirmee"])

    def test_modele_anglais_donne(self):
        texte = ("Hi compte.fictif, You recently added " + ALIAS + " to your Instagram account. Please confirm this email "
                 "address so we can update your contact information. You may be asked to enter this confirmation code:\n483921\n")
        i = self.c.classer(DE, "Confirm your email address", texte)
        self.assertEqual("donner", i["decision"])

    def test_mail_complet_donne_au_bon_alias(self):
        r = self.c.classer_mail(self.mail())
        self.assertEqual(("donner", ALIAS), (r["decision"], r["alias"]))

    def test_adresse_confirmee_differente_du_destinataire_gardee(self):
        r = self.c.classer_mail(self.mail(adresse_corps="perso.du.clipper@example.invalid"))
        self.assertEqual("garder", r["decision"])
        self.assertIsNone(r["code"])

    def test_jamais_avec_mot_de_passe_telephone_ou_2fa(self):
        for ajout in (" Réinitialisez aussi votre mot de passe.", " Ajoutez un numéro de téléphone.",
                      " Activez la double authentification.", " Si ce n'était pas vous, sécurisez le compte."):
            i = self.c.classer(DE, SUJET, corps(ajout=ajout))
            self.assertNotEqual("donner", i["decision"], ajout)

    def test_expediteur_hors_instagram_pas_ce_modele(self):
        i = self.c.classer("Quelqu'un <faux@example.invalid>", SUJET, corps())
        self.assertNotEqual("donner", i["decision"])


class CodeGardeDansAlerteTests(unittest.TestCase):
    def setUp(self):
        self.c = load_codes()
        self.now = datetime(2026, 10, 23, 10, 38, tzinfo=timezone.utc)
        self.c._maintenant = lambda: self.now

    def test_alerte_dit_qu_un_code_est_garde(self):
        garde = {"alias": ALIAS, "decision": "garder", "libelle": "e-mail ajouté ou changé",
                 "date": (self.now - timedelta(minutes=6)).isoformat()}
        texte = self.c.texte_code_absent("100", {ALIAS}, "auto", False, gardes=[garde])
        self.assertIn("aucun code donné", texte)
        self.assertIn("il y a 6 min", texte)
        self.assertIn("e-mail ajouté ou changé", texte)
        self.assertNotIn("rien n'est arrivé", texte)

    def test_sans_code_garde_inchange(self):
        texte = self.c.texte_code_absent("100", {ALIAS}, "auto", False)
        self.assertIn("rien n'est arrivé", texte)


if __name__ == "__main__":
    unittest.main()
