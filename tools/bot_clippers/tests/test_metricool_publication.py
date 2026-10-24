"""Exercise the pure publisher without importing service/Google dependencies."""
import ast
import unittest
import unicodedata
from pathlib import Path


class MetricoolPublicationTests(unittest.TestCase):
    def test_preserve_columns_and_publish_only_real_measurement_time(self):
        source = Path(__file__).resolve().parents[1] / "pilotage.py"
        tree = ast.parse(source.read_text())
        definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name in ("_txt", "_jours_txt", "lignes_comptes_app")]
        namespace = {"unicodedata": unicodedata}
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), namespace)
        publisher = namespace["lignes_comptes_app"]
        args = ({"1": "clipper"}, lambda uid: ["talent"], {}, lambda uid: "Test", {},
                {"talent": {"followers": 500, "followers_verified_at": "2026-10-17T10:00:00+00:00"}})
        row = publisher(*args)[0]
        self.assertEqual(["clipper", "Test", "", "1", "talent", "", "500", "", "", "", ""], row[:11])
        self.assertEqual("2026-10-17T10:00:00+00:00", row[11])
        no_proof = publisher(*args[:-1], {"talent": {"followers": 500}})[0]
        self.assertEqual("", no_proof[11])


if __name__ == "__main__":
    unittest.main()
