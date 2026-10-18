"""18/10 : identifiants du compte 1 dans le salon perso dès l'envoi (règles gelées E7, C10), contrôles de !remettre-compte1."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onboarding  # noqa: E402
import remise_compte1  # noqa: E402

LIGNE = {"handle": "neuf_un", "gerant": "Mavie", "creatrice": "Sarah", "etat": next(iter(onboarding.A_CREER)),
         "mail": "x@exemple.test", "mdp": "Secret123"}


class IdentifiantsTests(unittest.TestCase):
    def _lancer(self, lignes, lecteurs_ok=True, gerant="Mavie"):
        async def lire():
            return lignes

        def lecteurs(*a, **k):
            if not lecteurs_ok:
                raise remise_compte1.Retenue("Un lecteur non autorisé")
        with patch.object(onboarding, "lire_comptes", lire), patch.object(remise_compte1, "verifier_lecteurs", lecteurs), \
                patch.object(remise_compte1.parcours, "_onb", lambda uid: {"gerant": gerant}):
            return asyncio.run(remise_compte1.identifiants_surs(N(), N(), "7", "neuf_un", {"creatrice": "Sarah"}, set(),
                                                                lambda m: False))

    def test_salon_sur_et_ligne_a_lui(self):
        self.assertEqual(self._lancer([LIGNE]), ("x@exemple.test", "Secret123"))

    def test_lecteur_non_autorise_pas_de_secret(self):
        self.assertIsNone(self._lancer([LIGNE], lecteurs_ok=False))

    def test_ligne_d_un_autre_pas_de_secret(self):
        self.assertIsNone(self._lancer([LIGNE], gerant="Thia"))
        self.assertIsNone(self._lancer([LIGNE, dict(LIGNE)]))

    def test_modele_complet(self):
        texte = remise_compte1.modele("<@7>", "neuf_un", "x@exemple.test", "Secret123")
        for morceau in ("`neuf_un`", "`x@exemple.test`", "`Secret123`", "!code"):
            self.assertIn(morceau, texte)


if __name__ == "__main__":
    unittest.main()
