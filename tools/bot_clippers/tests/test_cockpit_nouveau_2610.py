"""26/10 (Gaëtan, Cockpit : « s'il est attribué à Jade, dans mon dashboard il est directement attribué à Jade aussi, avec New à
côté ») : le Cockpit lit l'onglet « Parcours » pour dater l'arrivée ; le bot le réécrit à la fin de chaque arrivée, pas seulement au
digest du matin, et jamais au prix de l'arrivée. Données fictives, sans réseau."""
import asyncio
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_assistant_simplifie_1810 import extraire  # noqa: E402


class RafraichirParcoursTests(unittest.TestCase):
    def ns(self, ecrire):
        return extraire("bot_discord.py", {"rafraichir_parcours_arrivee", "PARCOURS_ARRIVEE_TIMEOUT_S"},
                        {"asyncio": asyncio, "journal": logging.getLogger("test"), "ecrire_onglet_parcours": ecrire})

    def test_onglet_ecrit_a_l_arrivee(self):
        ecrire = AsyncMock(return_value=12)
        self.assertTrue(asyncio.run(self.ns(ecrire)["rafraichir_parcours_arrivee"]("1")))
        ecrire.assert_awaited_once()

    def test_echec_journalise_jamais_leve(self):
        ecrire = AsyncMock(side_effect=RuntimeError("Sheets indisponible"))
        with self.assertLogs("test", level="WARNING") as logs:
            self.assertFalse(asyncio.run(self.ns(ecrire)["rafraichir_parcours_arrivee"]("1")))
        self.assertIn("Onglet Parcours après l'arrivée de 1", logs.output[0])

    def test_rien_ecrit_vaut_faux(self):
        self.assertFalse(asyncio.run(self.ns(AsyncMock(return_value=0))["rafraichir_parcours_arrivee"]("1")))

    def test_appele_a_la_fin_de_l_arrivee(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        corps = src[src.index("async def onboarder_membre("):src.index("\nasync def rattraper_parcours_non_demarres(")]
        appel = corps.index("await rafraichir_parcours_arrivee(uid_m)")
        self.assertLess(corps.index("attribution.resoudre_blocage(uid_m)"), appel, "après que l'arrivée est faite")
        self.assertLess(appel, corps.index("return (f\"{'🆕' if cree_c else '✅'}"), "avant le bilan")


if __name__ == "__main__":
    unittest.main()
