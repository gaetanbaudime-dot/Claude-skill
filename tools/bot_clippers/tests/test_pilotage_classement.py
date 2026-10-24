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
        ns = functions("pilotage.py", {"_txt", "_jours_txt", "lignes_comptes_app"}, {"unicodedata": unicodedata})
        rows = ns["lignes_comptes_app"]({"1": "cle"}, lambda uid: ["growth1", "private", "growth2"],
            {}, lambda uid: "Test", {}, {}, numero_prive=lambda uid: 2)
        self.assertEqual(["1", "2", "3"], [r[3] for r in rows])
        self.assertEqual(["croissance", "privé", "croissance"], [r[12] for r in rows])
        self.assertTrue(all(len(r) == 14 for r in rows))

    def test_reels_par_jour_column_for_the_app(self):
        # 24/10 : la colonne « Reels par jour (17 j) » de « Comptes app » (cadence 7 j et prime volume de l'app des clippers)
        ns = functions("pilotage.py", {"_txt", "_jours_txt", "lignes_comptes_app"}, {"unicodedata": unicodedata})
        rows = ns["lignes_comptes_app"]({"1": "cle"}, lambda uid: ["growth1"], {}, lambda uid: "Test", {},
            {"growth1": {"jours": {"2026-10-22": 2, "2026-10-20": 3, "2026-10-21": 0}}})
        self.assertEqual("2026-10-20:3 2026-10-22:2", rows[0][13])
        self.assertEqual("", ns["_jours_txt"](None))
        empty = ns["lignes_comptes_app"]({"1": "cle"}, lambda uid: [], {}, lambda uid: "Test", {}, {})
        self.assertEqual(14, len(empty[0]))

    def test_reels_par_jour_counts_paris_days_in_window(self):
        instant = lambda t: datetime.fromisoformat(t) if t else None
        ns = functions("dashboard.py", {"reels_par_jour"}, {
            "_instant": instant, "_paris": lambda dt: dt.astimezone(timezone(timedelta(hours=2))), "timedelta": timedelta,
            "REELS_PAR_JOUR_JOURS": 17, "date": date,
        })
        serie = {"reels": {
            "a": {"publie": "2026-10-23T21:30:00+00:00"},   # 23h30 à Paris le 23
            "b": {"publie": "2026-10-23T22:30:00+00:00"},   # 0h30 à Paris : le 24
            "c": {"publie": "2026-10-24T08:00:00+00:00"},
            "d": {"publie": "2026-10-07T12:00:00+00:00"},   # hors des 17 jours
            "e": {"publie": ""}, "f": "illisible",
        }}
        self.assertEqual({"2026-10-23": 1, "2026-10-24": 2}, ns["reels_par_jour"](serie, date(2026, 10, 24)))
        self.assertEqual({}, ns["reels_par_jour"](None, date(2026, 10, 24)))

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
