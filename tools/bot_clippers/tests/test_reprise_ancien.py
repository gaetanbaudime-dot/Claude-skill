"""18/10 : `!reprise @membre Créatrice` — historique à vie d'un ancien clipper écrit d'après ce que le bot connaît. Cas fictifs."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reprise_ancien  # noqa: E402
from process_store import Bloque, Store  # noqa: E402

PROV = {"source": "discord-message:1", "par": "9", "date": "2026-10-18T09:45:00+00:00"}


class RepriseTests(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dossier.name) / "process.sqlite3")

    def tearDown(self):
        self.dossier.cleanup()

    def test_zero_compte_debloque_l_allocation(self):
        with self.assertRaises(Bloque):                                  # avant : bloqué comme Moutakabirou
            self.store.reserve("7", [])
        r = reprise_ancien.reprendre(self.store, "7", [], PROV)
        self.assertEqual(r["comptes"], 0)
        self.store.reserve("7", ["neuf_un", "neuf_deux", "neuf_trois"])  # les trois places sont là
        with self.assertRaises(Bloque):
            self.store.reserve("7", ["neuf_quatre"])

    def test_comptes_connus_comptent_dans_les_trois(self):
        h = reprise_ancien.handles_connus("7", {"clippers": {"7": {"comptes": ["@Ancien_Un"], "acces": [{"handle": "ancien_deux"}]}}}, {})
        self.assertEqual(h, ["ancien_deux", "ancien_un"])
        r = reprise_ancien.reprendre(self.store, "7", h, PROV)
        self.assertEqual(r["comptes"], 2)
        self.store.reserve("7", ["neuf_un"])
        with self.assertRaises(Bloque):
            self.store.reserve("7", ["neuf_deux"])

    def test_jamais_diminue_ni_vole(self):
        reprise_ancien.reprendre(self.store, "8", ["pris_ailleurs"], PROV)
        with self.assertRaises(Bloque):                                  # @ d'un autre clipper : refus
            reprise_ancien.reprendre(self.store, "7", ["pris_ailleurs"], PROV)
        reprise_ancien.reprendre(self.store, "7", ["a_lui"], PROV)
        r = reprise_ancien.reprendre(self.store, "7", [], PROV)           # relancée sans @ : rien n'est retiré
        self.assertEqual((r["comptes"], r["deja"]), (1, True))

    def test_depart_avec_lien_refuse(self):
        self.store.put("sortie:7", {"lien": "x"})
        with self.assertRaises(Bloque):
            reprise_ancien.reprendre(self.store, "7", [], PROV)

    def test_provenance_obligatoire(self):
        with self.assertRaises(Bloque):
            reprise_ancien.reprendre(self.store, "7", [], {"source": "", "par": "9", "date": "x"})


if __name__ == "__main__":
    unittest.main()
