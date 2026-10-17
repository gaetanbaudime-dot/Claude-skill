"""Contrat des fiches : rôles indépendants de l'ordre et sept jours clos."""
import ast
import unittest
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


def functions(file, names, namespace):
    source = Path(__file__).resolve().parents[1] / file
    nodes = [n for n in ast.parse(source.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


class ClassementTests(unittest.TestCase):
    def test_role_prive_2_and_legacy_column_positions(self):
        ns = functions("pilotage.py", {"_txt", "lignes_comptes_app"}, {"unicodedata": unicodedata})
        rows = ns["lignes_comptes_app"]({"1": "cle"}, lambda uid: ["growth1", "private", "growth2"],
            {}, lambda uid: "Test", {}, {}, numero_prive=lambda uid: 2)
        self.assertEqual(["1", "2", "3"], [r[3] for r in rows])
        self.assertEqual(["croissance", "privé", "croissance"], [r[12] for r in rows])
        self.assertTrue(all(len(r) == 13 for r in rows))

    def test_recent_views_exclude_today_and_older_than_seven_days(self):
        instant = lambda t: datetime.fromisoformat(t) if t else None
        midnight = lambda d: datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        ns = functions("dashboard.py", {"_reels_recents"}, {
            "_instant": instant, "_minuit": midnight, "timedelta": timedelta, "_Ctx": SimpleNamespace,
        })
        ctx = SimpleNamespace(j0=date(2026, 10, 17), maintenant=instant("2026-10-17T10:00:00+00:00"))
        reel = lambda d, v: {"publie": d, "vues": [["2026-10-17T09:00:00+00:00", v]]}
        row = {"rh": 1, "r7": 2, "serie": {"reels": {
            "old": reel("2026-10-09T23:59:00+00:00", 999),
            "first": reel("2026-10-10T00:00:00+00:00", 100),
            "last": reel("2026-10-16T23:59:00+00:00", 200),
            "today": reel("2026-10-17T00:00:00+00:00", 888),
        }}}
        self.assertEqual((1, 2, 300), ns["_reels_recents"](ctx, row))


if __name__ == "__main__":
    unittest.main()
