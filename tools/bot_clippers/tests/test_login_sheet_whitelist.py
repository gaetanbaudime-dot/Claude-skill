"""Do not process operational cockpit sheets as Instagram account credential rows."""
import ast
from pathlib import Path
import unicodedata
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "onboarding.py"


class LoginSheetRecognitionTests(unittest.TestCase):
    def setUp(self):
        module = ast.parse(SOURCE.read_text(encoding="utf-8"))
        wanted = {"en_tete_reconnu", "_exclus"}
        nodes = [node for node in module.body
                 if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.ns = {
            "_colonnes_trouvees": lambda columns: {str(x): i for i, x in enumerate(columns)},
            "_norm": lambda x: "".join(c for c in unicodedata.normalize("NFD", str(x).casefold())
                                          if unicodedata.category(c) != "Mn"),
            "ONGLETS_EXCLUS": "Gaetan, Backup, Dashboard",
            "ONGLETS_VUES_NON_COMPTES": (
                "Clippers · 360", "Référentiel clippers", "Scale · Plan 100",
                "Stats verticales", "Comptes Marketing", "Équipes Marketing",
                "Dashboard · Pilotage",
            ),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "onboarding_subset", "exec"), self.ns)

    def test_real_login_sheet_requires_email_and_password(self):
        self.assertTrue(self.ns["en_tete_reconnu"](["etat", "handle", "gerant", "mail", "mdp"]))
        self.assertFalse(self.ns["en_tete_reconnu"](["etat", "handle", "gerant", "app"]))
        self.assertFalse(self.ns["en_tete_reconnu"](["etat", "handle", "gerant", "mail"]))

    def test_cockpit_views_are_always_excluded(self):
        excluded = self.ns["_exclus"]()
        self.assertIn(self.ns["_norm"]("Clippers · 360"), excluded)
        self.assertIn(self.ns["_norm"]("Référentiel clippers"), excluded)
        self.assertIn(self.ns["_norm"]("Scale · Plan 100"), excluded)
        self.assertIn(self.ns["_norm"]("Dashboard · Pilotage"), excluded)


if __name__ == "__main__":
    unittest.main()
