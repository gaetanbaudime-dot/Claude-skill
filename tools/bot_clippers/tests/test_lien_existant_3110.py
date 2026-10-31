"""31/10 (Clarisse, TL : compte 3 retenu par « Lien préexistant sans journal » alors que son lien de clipping tourne) : un clipper qui
a déjà un lien vivant à son nom pour sa créatrice le garde. Cas fictifs, sans réseau."""
from pathlib import Path
from types import SimpleNamespace as N
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onboarding
import paie_clics


def liens(**infos):
    return {"liens": infos}


class LienExistantTests(unittest.IsolatedAsyncioTestCase):
    def test_qui_est_repris(self):
        d = liens(a={"uid": "42", "url": "https://exemple.test/chloe-fictive/13"},
                  b={"uid": "42", "url": "https://exemple.test/sarah-fictive/2", "creatrice": "Sarah"},
                  c={"uid": "43", "url": "https://exemple.test/chloe-fictive/9", "creatrice": "Chloé", "desactive": True})
        with patch.object(paie_clics, "_lire", return_value=d):
            self.assertEqual(("a", "https://exemple.test/chloe-fictive/13"), onboarding.lien_existant("42", "Chloé"))
            self.assertEqual(("b", "https://exemple.test/sarah-fictive/2"), onboarding.lien_existant("42", "Sarah"))
            self.assertIsNone(onboarding.lien_existant("42", "Sophie"))         # pivot : jamais le lien d'une autre créatrice
            self.assertIsNone(onboarding.lien_existant("43", "Chloé"))          # désactivé
        deux = liens(a={"uid": "42", "url": "https://exemple.test/chloe-fictive/13"},
                     b={"uid": "42", "url": "https://exemple.test/chloe-fictive/14", "creatrice": "Chloé"})
        with patch.object(paie_clics, "_lire", return_value=deux):
            self.assertIsNone(onboarding.lien_existant("42", "Chloé"))          # deux liens : rapprochement humain

    async def test_attribuer_reprend_sans_creer(self):
        etat = {"clippers": {"42": {"creatrice": "Chloé"}}}
        ecrit = {}
        cree = AsyncMock()
        with patch.object(onboarding, "_lire_etat", return_value=etat), \
                patch.object(onboarding, "_ecrire_etat", side_effect=lambda e: ecrit.update(e)), \
                patch.object(onboarding, "lien_existant", return_value=("a", "https://exemple.test/chloe-fictive/13")), \
                patch.object(onboarding.process_adapters, "attribuer", cree):
            bilan = await onboarding.attribuer_lien(N(id=42), "Chloé")
        self.assertEqual("https://exemple.test/chloe-fictive/13", bilan["lien"])
        cree.assert_not_awaited()
        self.assertTrue(ecrit["clippers"]["42"]["liens_prets"])
        etat2 = {"clippers": {"42": {"creatrice": "Chloé", "lien": "https://exemple.test/autre"}}}
        with patch.object(onboarding, "_lire_etat", return_value=etat2), \
                patch.object(onboarding, "lien_existant", return_value=("a", "https://exemple.test/chloe-fictive/13")), \
                patch.object(onboarding.process_adapters, "attribuer", cree):
            await onboarding.attribuer_lien(N(id=42), "Chloé")
        cree.assert_awaited_once()                                              # une fiche qui a déjà son lien : le chemin habituel


if __name__ == "__main__":
    unittest.main()
