"""26/10 (Gaëtan : « Enlève Rianah de tous les trucs aussi, elle est au salaire ») : Rianah est au fixe, clipping compris, même
avec un ancien `!paie clic` ; elle sort du classement du lundi et du parrainage des cinq premiers ; elle garde son app.
Cas fictifs, sans réseau ni Discord."""
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paie_clics  # noqa: E402

REGISTRE = {
    "1": {"prenom": "rianah", "date": "2026-09-10", "paie": "clic", "paie_le": "2026-10-13"},
    "2": {"prenom": "simon", "date": "2026-10-12"},
    "3": {"prenom": "caroline", "date": "2026-09-01"},
    "4": {"prenom": "rianah", "date": "2026-09-10", "paie": "clic", "paie_le": "2026-10-27"},
}
NOMS = {"1": "Rianah Clipping Chloé", "2": "Simon", "3": "Caroline", "4": "Rianah"}


def deps():
    return {"lire_json": lambda chemin, defaut: REGISTRE, "FICHIER_EQUIPES": "equipes.json",
            "membre_par_id": lambda uid: SimpleNamespace(display_name=NOMS[str(uid)]) if str(uid) in NOMS else None}


class RegimeTests(unittest.TestCase):
    def test_rianah_au_fixe_malgre_le_paie_clic_du_13_10(self):
        with patch.dict(paie_clics._deps, deps()):
            self.assertEqual("fixe", paie_clics.regime("1"))
            self.assertEqual("", paie_clics.debut_clic("1"), "au fixe : aucune visite payée au clic")
            self.assertTrue(paie_clics.au_salaire("1"))

    def test_un_paie_pose_depuis_le_26_10_passe_encore_par_dessus(self):
        with patch.dict(paie_clics._deps, deps()):
            self.assertEqual("clic", paie_clics.regime("4"))

    def test_les_autres_ne_bougent_pas(self):
        with patch.dict(paie_clics._deps, deps()):
            self.assertEqual("clic", paie_clics.regime("2"))
            self.assertEqual("fixe", paie_clics.regime("3"))
            self.assertFalse(paie_clics.au_salaire("2"))

    def test_rianah_garde_son_app(self):
        self.assertIn("rianah", paie_clics.PAIE_SALAIRE)
        self.assertNotIn("rianah", paie_clics.CLICS_EXCLURE)

    def test_registre_illisible_rien_ne_tombe(self):
        with patch.dict(paie_clics._deps, {"lire_json": None}):
            self.assertFalse(paie_clics.au_salaire("1"))


class ClassementTests(unittest.TestCase):
    def setUp(self):
        self.d = {"liens": {"a": {"uid": "1"}, "b": {"uid": "2"}, "c": {"uid": "3"}}}
        self.valeurs = {"a": 900, "b": 50, "c": 400}

    def classer(self):
        with patch.dict(paie_clics._deps, deps()), \
                patch.object(paie_clics, "somme", lambda d_, lids, debut, fin: {"payes": sum(self.valeurs[x] for x in lids)}):
            texte = paie_clics.texte_classement(self.d, lambda u: NOMS[u], date(2026, 10, 25))
            top = paie_clics.top_uids(self.d, date(2026, 10, 25))
        return texte, top

    def test_rianah_hors_du_top_et_du_parrainage(self):
        texte, top = self.classer()
        self.assertNotIn("Rianah", texte)
        self.assertIn("1. **Caroline**", texte)
        self.assertEqual(["3", "2"], top)
        self.assertIn("2 clipper(s) ont fait des visites", texte)


if __name__ == "__main__":
    unittest.main()
