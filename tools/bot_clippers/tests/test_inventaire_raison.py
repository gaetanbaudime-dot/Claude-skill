"""23/10 : un inventaire GAML incomplet bloquait toute création de lien sans dire pourquoi. La raison est maintenant dans le journal."""
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paie_clics as p  # noqa: E402


class RaisonDeLIncompletude(unittest.IsolatedAsyncioTestCase):
    async def test_page_rendue_identique_au_plafond_du_forfait(self):
        with patch.object(p, "_requete", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])), patch.object(p, "FORFAIT_LIENS_GAML", 2):
            with self.assertLogs("clics", level="WARNING") as journal:
                r = await p.liens_gaml()
        self.assertFalse(r.complete)
        self.assertIn("Inventaire GAML incomplet", journal.output[0])
        self.assertIn("page 2 : 2 lien(s), tous déjà lus", journal.output[0])

    async def test_page_rendue_identique_sous_le_forfait_le_dit_en_info(self):
        with patch.object(p, "_requete", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])), patch.object(p, "FORFAIT_LIENS_GAML", 50):
            with self.assertNoLogs("clics", level="WARNING"):
                with self.assertLogs("clics", level="INFO") as journal:
                    r = await p.liens_gaml()
        self.assertTrue(r.complete)
        self.assertIn("le serveur ignore la page", journal.output[0])

    async def test_page_refusee(self):
        with patch.object(p, "_requete", AsyncMock(side_effect=[[{"id": "a"}], RuntimeError("GAML 500")])):
            with self.assertLogs("clics", level="WARNING") as journal:
                r = await p.liens_gaml()
        self.assertFalse(r.complete)
        self.assertIn("page 2 refusée", journal.output[-1])

    async def test_jamais_de_page_vide(self):
        pages = [[{"id": str(i)}] for i in range(1, 12)]
        with patch.object(p, "_requete", AsyncMock(side_effect=pages)):
            with self.assertLogs("clics", level="WARNING") as journal:
                r = await p.liens_gaml()
        self.assertFalse(r.complete)
        self.assertIn("pas de page vide avant la page 10", journal.output[-1])

    async def test_inventaire_complet_ne_dit_rien(self):
        with patch.object(p, "_requete", AsyncMock(side_effect=[[{"id": "a"}], []])):
            with self.assertNoLogs("clics", level="WARNING"):
                r = await p.liens_gaml()
        self.assertTrue(r.complete)


if __name__ == "__main__":
    unittest.main()
