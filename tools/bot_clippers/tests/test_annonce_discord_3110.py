"""31/10 : `!annonce discord-<serveur>` garde sa source (Gaëtan cherche ses leads sur Discord). Sans réseau."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import web_candidature as w


class AnnonceTests(unittest.TestCase):
    def test_sources(self):
        with patch.object(w, "actif", return_value=True), patch.object(w, "WEB_URL_PUBLIQUE", "https://exemple.test"):
            self.assertIn("/candidature?src=discord-serveur-fictif", w.texte_annonce_telegram("discord-serveur-fictif"))
            self.assertIn("/candidature?src=disboard", w.texte_annonce_telegram("Disboard"))
            self.assertIn("/candidature?src=tg-jobs-fictifs", w.texte_annonce_telegram("jobs fictifs"))
            texte = w.texte_annonce_telegram("tg-jobs")
        self.assertIn("Tu crées des comptes Instagram avec les @ qu'on te donne", texte)
        self.assertIn("18 ans minimum.", texte)
        self.assertIn("`!annonce discord-<serveur>`", w.reponse_commande_annonce(""))


if __name__ == "__main__":
    unittest.main()
