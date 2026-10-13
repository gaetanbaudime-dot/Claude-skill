"""Non-destructive regression checks for the G&M marketing Discord bot.

Run from tools/bot_clippers: python -m unittest discover -s tests
No Discord token, Gmail account or live Instagram access is needed.
"""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    return ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)


def function(name, function_name):
    tree = module(name)
    return next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name == function_name)


class LifecycleSafetyTests(unittest.TestCase):
    def test_all_lifecycle_files_compile(self):
        for name in ("bot_discord.py", "appel.py", "sortie_auto.py"):
            with self.subTest(name=name):
                compile((ROOT / name).read_text(encoding="utf-8"), name, "exec")

    def test_central_guard_rejects_unattended_removal_before_any_side_effect(self):
        node = function("bot_discord.py", "sortir_membre")
        code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                       "extracted_sortir_membre.py", "exec")
        ns = {"os": os, "journal": logging.getLogger("test")}
        exec(code, ns)
        class Member:
            id = 42
            # Intentionally no guild, roles or permissions. The guard must return
            # before attempting ANY Discord, Sheets, GAML or file access.
        old = os.environ.pop("SORTIES_AUTO_AUTORISEES", None)
        try:
            result = asyncio.run(ns["sortir_membre"](Member(), "faux positif",
                                                       par=None, pool=True, expulser=True))
            self.assertEqual(result["roles"], 0)
            self.assertEqual(result["comptes"], 0)
            self.assertEqual(result["liens"], 0)
            self.assertFalse(result["expulse"])
            self.assertTrue(result["refus"])
        finally:
            if old is not None:
                os.environ["SORTIES_AUTO_AUTORISEES"] = old

    def test_reviewed_calls_cannot_be_reprocessed(self):
        node = function("appel.py", "a_sortir")
        code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                       "extracted_a_sortir.py", "exec")
        ns = {"datetime": datetime, "timezone": timezone, "timedelta": timedelta,
              "HEURES": 48,
              "_dt": lambda val: datetime.fromisoformat(val) if val else None}
        exec(code, ns)
        now = datetime(2026, 10, 13, tzinfo=timezone.utc)
        pending = {"date": "2026-10-10T00:00:00+00:00"}
        queued = dict(pending, verification_humaine="2026-10-12T12:00:00+00:00")
        result = ns["a_sortir"]({"appels": {"reviewed": queued, "pending": pending}}, now)
        self.assertEqual([uid for uid, _ in result], ["pending"])

    def test_reminder_does_not_threaten_a_clipper(self):
        names = {n.targets[0].id: n.value for n in module("appel.py").body
                 if isinstance(n, ast.Assign) and len(n.targets) == 1
                 and isinstance(n.targets[0], ast.Name)}
        template = ast.literal_eval(names["TEXTE_APPEL"])
        self.assertNotIn("tu sors du serveur", template)
        self.assertIn("manager", template)

    def test_first_account_exit_is_preceded_by_manager_review_guard(self):
        node = function("sortie_auto.py", "executer")
        source = ast.get_source_segment((ROOT / "sortie_auto.py").read_text(encoding="utf-8"), node)
        self.assertIn("if not RETRAIT_AUTOMATIQUE:", source)
        self.assertIn("validation manager requise", source)
        self.assertLess(source.index("if not RETRAIT_AUTOMATIQUE:"),
                        source.index('await _deps["sortir"]'))


if __name__ == "__main__":
    unittest.main()
