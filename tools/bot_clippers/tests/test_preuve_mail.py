"""24/10 : un mail d'Instagram qui salue le compte prouve qu'il est créé (Esperance, Pierre listés « compte 1 pas créé »).
Modèles synthétiques : aucun vrai mail, alias, pseudo ni code."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
import sys
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import preuve_mail  # noqa: E402

ALIAS = "alias.fictif@example.invalid"
QUAND = datetime(2026, 10, 23, 10, 32, tzinfo=timezone.utc)


def mail(salut="Bonjour compte.vrai,", de="Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>", quand=QUAND):
    m = EmailMessage()
    m["From"] = de
    m["To"] = ALIAS
    m["Subject"] = "123456 est votre code Instagram"
    m["Date"] = format_datetime(quand)
    m["Message-ID"] = "<preuve@example.invalid>"
    m["Authentication-Results"] = "mx.google.com; dkim=pass header.d=mail.instagram.com"
    m.set_content(salut + " Quelqu'un a tenté de se connecter à votre compte Instagram.")
    return m


class LectureTests(unittest.TestCase):
    def test_salut_lu(self):
        self.assertEqual((ALIAS, "compte.vrai", QUAND), preuve_mail.lire_mail(mail()))

    def test_sans_salut_rien(self):
        self.assertIsNone(preuve_mail.lire_mail(mail(salut="Bonjour,")))

    def test_expediteur_hors_instagram_rien(self):
        self.assertIsNone(preuve_mail.lire_mail(mail(de="Instagram <faux@example.invalid>")))


class TraitementTests(unittest.TestCase):
    def setUp(self):
        self.fichier = {}
        self.renommer = AsyncMock(return_value=("compte.prevu", ""))
        self.fermer = AsyncMock(return_value=True)
        self.admin = AsyncMock()
        self.info = {"uid": "100", "n": 1, "handle": "compte.prevu", "ouverte": (QUAND - timedelta(days=4)).isoformat(),
                     "cree": False, "recycle": False, "prenom": "Prénom"}
        preuve_mail._deps.clear()
        preuve_mail.configurer({"lire_json": lambda f, d: dict(self.fichier), "ecrire_json": lambda f, d: self.fichier.update(d),
                                "FICHIER": "preuve.json", "proprietaire": lambda a: dict(self.info) if a == ALIAS else None,
                                "renommer": self.renommer, "fermer": self.fermer, "admin": self.admin})

    def lancer(self, pseudo="compte.vrai", quand=QUAND):
        return asyncio.run(preuve_mail.traiter(ALIAS, pseudo, quand))

    def test_pseudo_different_renomme_puis_ferme(self):
        texte = self.lancer()
        self.renommer.assert_awaited_once_with("100", 1, "compte.vrai")
        self.fermer.assert_awaited_once_with("100", 1)
        self.assertIn("compte.prevu", texte)
        self.assertIn("étape fermée", texte)

    def test_meme_pseudo_ferme_sans_renommer(self):
        self.lancer(pseudo="compte.prevu")
        self.renommer.assert_not_awaited()
        self.fermer.assert_awaited_once()

    def test_une_seule_fois_par_mail(self):
        self.lancer()
        self.lancer()
        self.assertEqual(1, self.fermer.await_count)

    def test_mail_plus_ancien_que_l_etape_ignore(self):
        self.lancer(quand=QUAND - timedelta(days=10))
        self.fermer.assert_not_awaited()

    def test_compte_recycle_ou_deja_cree_ignore(self):
        for cle in ("recycle", "cree"):
            self.info = dict(self.info, **{cle: True})
            self.assertEqual("", self.lancer(pseudo=f"autre.{cle}"))
        self.fermer.assert_not_awaited()

    def test_adresse_sans_proprietaire_ignoree(self):
        self.assertEqual("", asyncio.run(preuve_mail.traiter("autre@example.invalid", "x.y", QUAND)))
        self.fermer.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
