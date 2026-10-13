"""Immutable UID joins for the marketing scale cockpit."""
from datetime import date
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ops_identity


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.teams = {
            "Sophie": {"tl": "900", "vas": ["100", "101"], "manager": "800",
                        "noms": {"900": "Mathieu", "100": "Thia", "101": "Thia", "800": "Manager"}}
        }
        self.handles = {
            "100": ["ig.thia.one", "ig.thia.two", "ig.thia.private"],
            "101": ["ig.thia.other", "ig.second", "ig.prive"],
        }
        self.ig_data = {
            h: {"creatrice": "Sophie", "etat": "GOOD"}
            for ids in self.handles.values() for h in ids
        }
        self.links = {"liens": {
            "link-100": {"uid": "100", "url": "https://gaml.fr/thia100", "creatrice": "Sophie"},
            "link-101": {"uid": "101", "url": "https://gaml.fr/thia101", "creatrice": "Sophie"},
        }}

    def rows(self, app_keys=None, measured_visits=None):
        return ops_identity.build_rows(
            app_keys or {"100": "private-auth-key-1"},
            self.teams, lambda uid: self.handles.get(uid, []), self.ig_data,
            self.links, lambda uid: {"900": "Mathieu", "800": "Manager", "100": "Thia", "101": "Thia"}.get(uid, ""),
            measured_visits=measured_visits, today=date(2026, 10, 13),
            reels_by_handle={"ig.thia.one": {"r7": 4}})

    def test_same_first_name_does_not_merge_owners(self):
        rows = {r[0]: r for r in self.rows()}
        self.assertIn("100", rows)
        self.assertIn("101", rows)
        self.assertIn("ig.thia.one", rows["100"])
        self.assertNotIn("ig.thia.other", rows["100"])
        self.assertIn("link-100", rows["100"][17])
        self.assertNotIn("link-101", rows["100"][17])
        self.assertEqual(rows["100"][4], "Mathieu")

    def test_app_key_and_credentials_are_never_exported(self):
        rows = self.rows()
        as_text = str(rows)
        self.assertNotIn("private-auth-key-1", as_text)
        self.assertFalse(any(any(key in c.lower() for key in
                                 ("mdp", "password", "otp", "2fa", "clé app"))
                             for c in ops_identity.COLUMNS))
        self.assertEqual(len(rows[0]), len(ops_identity.COLUMNS))

    def test_missing_visits_never_presented_as_zero(self):
        rows = {r[0]: r for r in self.rows(measured_visits=lambda _: None)}
        self.assertEqual(rows["100"][19], "")
        self.assertIn("Partiel", rows["100"][20])

    def test_no_tl_is_reported_not_assigned_by_name(self):
        t = {"Sophie": {"tl": None, "vas": ["100"], "manager": None, "noms": {"100": "Thia"}}}
        rows = ops_identity.build_rows(
            {"100": "key"}, t, lambda uid: self.handles.get(uid, []), self.ig_data,
            self.links, lambda uid: "Thia")
        self.assertIn("TL non assigné", rows[0][-1])


if __name__ == "__main__":
    unittest.main()
