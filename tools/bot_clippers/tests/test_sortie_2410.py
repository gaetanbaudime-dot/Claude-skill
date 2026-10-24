"""24/10 (Gaëtan, « !sortie meiji/laure/bab/randii raison ») : un pseudo avec « #👍 » est reconnu, un lien local déjà effacé dans
GAML n'empêche plus la sortie (archivé ici, visites dues gardées), un doute bloque toujours. Données fictives uniquement."""
import asyncio
from datetime import date
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import onboarding as o  # noqa: E402
import paie_clics as p  # noqa: E402
import process_adapters  # noqa: E402
from process_adapters import DepartAPI  # noqa: E402
from process_store import Bloque  # noqa: E402
from test_assistant_simplifie_1810 import extraire, normaliser  # noqa: E402


class Inventaire(list):
    complete = True


class NomTapeTests(unittest.TestCase):
    ns = extraire("bot_discord.py", {"membre_par_nom_tape"}, {"re": re, "normaliser": normaliser})

    def test_pseudo_avec_diese_et_emoji(self):
        laure = SimpleNamespace(display_name="Laure#👍", name="laure_x", global_name=None, bot=False)
        g = SimpleNamespace(members=[laure, SimpleNamespace(display_name="Lucas - Chloé", bot=False)])
        self.assertEqual((laure, "raison", []), self.ns["membre_par_nom_tape"](g, ["laure", "raison"]))

    def test_absent_du_serveur(self):
        g = SimpleNamespace(members=[SimpleNamespace(display_name="Lucas - Chloé", bot=False)])
        self.assertEqual((None, "", []), self.ns["membre_par_nom_tape"](g, ["bab", "raison"]))

    def test_message_si_personne(self):
        src = (ROOT / "bot_discord.py").read_text(encoding="utf-8")
        self.assertIn("Personne ne s'appelle", src)


class OrphelinsTests(unittest.TestCase):
    def setUp(self):
        self.stockes = {}
        self.store = SimpleNamespace(put=lambda k, v: self.stockes.__setitem__(k, v), get=lambda k: self.stockes.get(k, {}))

    def lancer(self, data, efface=True):
        with patch.object(p, "actif", return_value=True), \
                patch.object(p, "liens_gaml", AsyncMock(return_value=Inventaire([{"id": "vivant", "note": "Clipping X"}]))), \
                patch.object(p, "_lire", return_value=data), patch.object(p, "_ecrire"), \
                patch.object(p, "_aujourdhui", return_value=date(2026, 10, 24)), \
                patch.object(p, "garder_dus") as dus, \
                patch.object(o, "_lien_efface_gaml", AsyncMock(return_value=efface)), \
                patch.object(o, "_lire_etat", return_value={"clippers": {"42": {"comptes": ["compte.fictif"]}}}), \
                patch.object(process_adapters, "store", return_value=self.store):
            return asyncio.run(DepartAPI(None, "fictif").liens("42")), dus

    def test_lien_efface_dans_gaml_archive_ici_et_sortie_continue(self):
        data = {"liens": {"vivant": {"uid": "42"}, "efface": {"uid": "42", "depuis": "2026-10-01"}}}
        liens, dus = self.lancer(data)
        self.assertEqual(["vivant"], liens)
        self.assertTrue(data["liens"]["efface"]["archive"])
        self.assertEqual("42", data["liens"]["efface"]["uid"])                # l'historique de paie reste à lui
        dus.assert_called_once()
        self.assertEqual(["efface"], self.stockes["depart-orphelins:42"]["liens"])

    def test_doute_bloque_toujours(self):
        data = {"liens": {"vivant": {"uid": "42"}, "efface": {"uid": "42"}}}
        with self.assertRaisesRegex(Bloque, "rapprochement"):
            self.lancer(data, efface=False)

    def test_deja_archive_sans_nouvel_appel(self):
        data = {"liens": {"vivant": {"uid": "42"}, "vieux": {"uid": "42", "archive": True}}}
        liens, dus = self.lancer(data, efface=False)
        self.assertEqual(["vivant"], liens)
        dus.assert_not_called()


if __name__ == "__main__":
    unittest.main()
