"""Confirmations hors ligne : ordre, rôles, historiques et échecs sans mutation."""
import ast
import asyncio
import json
from copy import deepcopy
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from account_confirmations import prepare, check_database


def extract(name, names, ns):
    nodes = [n for n in ast.parse((ROOT / name).read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), name, "exec"), ns)
    return ns


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.onb = {"clippers": {"100": {"creatrice": "Chloé", "comptes": ["ancien", "growth", "growth.prv"],
            "acces": [{"handle": h, "mdp": f"fictif-{h}", "cree": True}
                      for h in ("ancien", "growth", "growth.prv", "real.backstage")],
            "lien": "https://example.test/5", "notes": ["conserver"]},
            "200": {"comptes": ["autre"], "acces": [{"handle": "autre"}]}},
            "livres": {"ancien": {"uid": "100"}}, "historique": ["conserver"]}
        self.onb["comptes_a_vie"] = {"100": [{"id": f"identity-{i}", "aliases": [h]}
            for i, h in enumerate(("ancien", "growth", "growth.prv", "real.backstage"))]}
        self.routes = {"100": {"dates": {}, "notes": ["conserver"], "reels": {"ancien": {"total": 5}}}}
        self.links = {"liens": {"l4": {"uid": "100", "url": "https://example.test/4"},
                                "l5": {"uid": "100", "url": "https://example.test/5"}}}
        self.c = {"uid": "100", "creatrice": "Chloé", "par": "Manager", "date": "2026-10-17T07:14:00+00:00",
                  "reference": "confirmation-fictive", "comptes": [
                      {"handle": "growth", "role": "croissance"},
                      {"handle": "growth.prv", "role": "croissance"},
                      {"handle": "real.backstage", "role": "prive"}], "lien": "https://example.test/4"}

    def test_prepare_preserves_history_credentials_and_other_users(self):
        originals = deepcopy((self.onb, self.routes, self.links))
        onb, routes, report = prepare(self.onb, self.routes, self.links, [self.c])
        self.assertEqual(originals, (self.onb, self.routes, self.links))
        f = onb["clippers"]["100"]
        self.assertEqual(["growth", "growth.prv", "real.backstage"], f["comptes"])
        self.assertEqual("fictif-growth", f["acces"][0]["mdp"])
        self.assertEqual("ancien", f["acces_archives"][0]["handle"])
        self.assertIn("ancien", {a for c in onb["comptes_a_vie"]["100"] for a in c["aliases"]})
        self.assertEqual(self.onb["clippers"]["200"], onb["clippers"]["200"])
        self.assertNotIn("200", onb["comptes_a_vie"])
        self.assertEqual(self.onb["comptes_a_vie"], onb["comptes_a_vie"])
        self.assertEqual({}, routes["100"]["dates"])
        self.assertEqual(self.routes["100"]["reels"], routes["100"]["reels"])
        self.assertNotIn("mdp", str(report))
        replay = prepare(onb, routes, self.links, [self.c])
        self.assertEqual((onb, routes), replay[:2])

    def test_missing_access_never_copies_credentials_from_another_handle(self):
        self.c["comptes"][2]["handle"] = "unknown.backstage"
        self.onb["comptes_a_vie"]["100"].append({"id": "identity-5", "aliases": ["unknown.backstage"]})
        before = deepcopy(self.onb)
        with self.assertRaisesRegex(ValueError, "accès existant unique"):
            prepare(self.onb, self.routes, self.links, [self.c])
        self.assertEqual(before, self.onb)

    def test_cli_backup_candidates_and_sqlite_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, data in (("onboarding.json", self.onb), ("parcours.json", self.routes), ("clics.json", self.links)):
                (root / name).write_text(json.dumps(data))
            (root / "confirmations.json").write_text(json.dumps([self.c]))
            database = root / "process_clippeur.sqlite3"
            with sqlite3.connect(database) as db:
                db.executescript("CREATE TABLE accounts(id TEXT,uid TEXT); CREATE TABLE aliases(handle TEXT,account_id TEXT); CREATE TABLE jobs(key TEXT,data TEXT);")
                for i, account in enumerate(self.c["comptes"]):
                    db.execute("INSERT INTO accounts VALUES(?,?)", (str(i), "100"))
                    db.execute("INSERT INTO aliases VALUES(?,?)", (account["handle"], str(i)))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            result = subprocess.run([sys.executable, str(ROOT / "account_confirmations.py"), "--data-dir", str(root),
                "--confirmations", str(root / "confirmations.json"), "--output-dir", str(root / "candidate")], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()})
            self.assertEqual(before["onboarding.json"], (root / "candidate/backup/onboarding.json").read_bytes())
            self.assertEqual(0o600, (root / "candidate/onboarding.candidate.json").stat().st_mode & 0o777)
            with sqlite3.connect(database) as db:
                db.execute("UPDATE accounts SET uid='200' WHERE id='0'")
            with self.assertRaisesRegex(ValueError, "propriétaire divergent"):
                check_database(database, [self.c])
            with sqlite3.connect(database) as db:
                db.execute("UPDATE accounts SET uid='100'")
                db.execute("INSERT INTO jobs VALUES(?,?)", ("liens:100:chloé", json.dumps({"lien": "https://example.test/5"})))
            with self.assertRaisesRegex(ValueError, "Job GAML divergent"):
                check_database(database, [self.c])

    def test_missing_lifetime_identity_blocks_without_fabricating_ids(self):
        del self.onb["comptes_a_vie"]
        with self.assertRaisesRegex(ValueError, "historique des identités"):
            prepare(self.onb, self.routes, self.links, [self.c])
        self.assertNotIn("comptes_a_vie", self.onb)

    def test_other_owner_and_wrong_link_owner_block(self):
        self.c["comptes"][0]["handle"] = "autre"
        with self.assertRaisesRegex(ValueError, "autre clipper"):
            prepare(self.onb, self.routes, self.links, [self.c])
        self.c["comptes"][0]["handle"] = "growth"
        self.links["liens"]["l4"]["uid"] = "200"
        with self.assertRaisesRegex(ValueError, "propriétaire"):
            prepare(self.onb, self.routes, self.links, [self.c])

    def test_real_order_functions_obey_roles_and_private_second_without_dates(self):
        private = extract("onboarding.py", {"_est_prive"}, {"_norm": str.lower,
                          "RE_PRIVE": re.compile(r"priv|secret|onlyme|perso")})["_est_prive"]
        ns = extract("parcours.py", {"ordre", "n_prive", "_comptes_ordonnes", "_comptes_ordonnes_05"},
                     {"PRIVE_EN_2": False, "onboarding": SimpleNamespace(_est_prive=private)})
        onb, routes, _ = prepare(self.onb, self.routes, self.links, [self.c])
        self.assertEqual(["growth", "growth.prv", "real.backstage"],
                         ns["_comptes_ordonnes"]("100", onb["clippers"]["100"], routes["100"]))
        self.c["comptes"] = [self.c["comptes"][0], self.c["comptes"][2]]
        onb, routes, _ = prepare(self.onb, self.routes, self.links, [self.c])
        self.assertEqual(2, ns["n_prive"](routes["100"]))
        self.assertEqual({}, routes["100"]["dates"])
        self.assertEqual(["growth", "real.backstage"],
                         ns["_comptes_ordonnes"]("100", onb["clippers"]["100"], routes["100"]))
        self.assertEqual("prive3", ns["ordre"]({"ordre": "prive2", "dates": {}}))

    def test_confirmed_link_blocks_stale_job_before_reservation_or_network(self):
        source = ast.parse((ROOT / "process_adapters.py").read_text())
        node = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "attribuer")
        for create, job in ((True, {}), (False, {"phase": "pret", "lien": "https://example.test/5"})):
            registry = SimpleNamespace(get=lambda key: job if key.startswith("liens:") else {})
            ns = {"store": lambda: registry, "Bloque": RuntimeError}
            exec(compile(ast.Module(body=[node], type_ignores=[]), "process_adapters.py", "exec"), ns)
            onboarding = SimpleNamespace(_lire_etat=lambda: {"clippers": {"100": {
                "lien_confirme": {"url": "https://example.test/4"}}}})
            with patch.dict(sys.modules, {"onboarding": onboarding, "paie_clics": SimpleNamespace()}):
                with self.assertRaisesRegex(RuntimeError, "rapprochement requis"):
                    asyncio.run(ns["attribuer"](SimpleNamespace(id=100), "Chloé", creer=create))


if __name__ == "__main__":
    unittest.main()
