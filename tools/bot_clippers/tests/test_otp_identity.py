"""Only uniquely verified active clippers may receive recovered mail aliases."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from otp_identity import unique_aliases


class OtpIdentityTests(unittest.TestCase):
    def setUp(self):
        self.roster = {"u100": {"creatrice": "Sophie", "prenom": "Diamondra", "active": True},
                       "u200": {"creatrice": "Sophie", "prenom": "Mathieu", "active": True},
                       "u300": {"creatrice": "Sarah", "prenom": "Diamondra", "active": True}}
        self.lines = [
            {"creatrice": "Sophie", "gerant": "Diamondra", "handle": "sophie.one", "mail": "one@icloud.com"},
            {"creatrice": "Sophie", "gerant": "Diamondra", "handle": "sophie.two", "mail": "two@icloud.com"},
            {"creatrice": "Sophie", "gerant": "Diamondra", "handle": "sophie.private", "mail": "three@icloud.com"},
            {"creatrice": "Sophie", "gerant": "Mathieu", "handle": "mathieu.one", "mail": "not-for-her@icloud.com"},
            {"creatrice": "Sarah", "gerant": "Diamondra", "handle": "sarah.one", "mail": "sarah@icloud.com"},
        ]

    def test_verified_owner_and_three_accounts(self):
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster, self.lines,
                                       {"sophie.one": {"u100"}})
        self.assertEqual(status, "matched")
        self.assertEqual(result, {"one@icloud.com", "two@icloud.com", "three@icloud.com"})
        self.assertNotIn("sarah@icloud.com", result)
        self.assertNotIn("not-for-her@icloud.com", result)

    def test_duplicate_first_name_same_creator_blocks(self):
        roster = dict(self.roster)
        roster["u999"] = {"creatrice": "Sophie", "prenom": "Diamondra", "active": True}
        result, status = unique_aliases("u100", "Sophie", "Diamondra", roster, self.lines, {})
        self.assertFalse(result)
        self.assertEqual(status, "ambiguous_or_not_in_roster")

    def test_existing_other_owner_blocks_all(self):
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster,
                                       self.lines, {"sophie.two": {"u200"}})
        self.assertFalse(result)
        self.assertEqual(status, "ownership_conflict")

    def test_not_registered_is_never_assumed_owner(self):
        result, status = unique_aliases("other", "Sophie", "Diamondra", self.roster, self.lines, {})
        self.assertFalse(result)
        self.assertEqual(status, "ambiguous_or_not_in_roster")

    def test_quatre_comptes_acceptes_sept_bloques(self):
        # 19/10 (Esperance) : un compte remplacé laisse une 4e ligne ; c'est normal. Au-delà de 6 : revue manuelle.
        more = self.lines + [{"creatrice": "Sophie", "gerant": "Diamondra",
                              "handle": "sophie.four", "mail": "four@icloud.com"}]
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster, more, {})
        self.assertEqual(status, "matched")
        self.assertIn("four@icloud.com", result)
        trop = self.lines + [{"creatrice": "Sophie", "gerant": "Diamondra", "handle": f"sophie.x{i}",
                              "mail": f"x{i}@icloud.com"} for i in range(7)]
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster, trop, {})
        self.assertFalse(result)
        self.assertEqual(status, "too_many_accounts")

    def test_alias_partage_entre_comptes_est_refuse(self):
        rows = self.lines + [{"creatrice": "Sarah", "gerant": "Mathieu", "handle": "sarah.two", "mail": "one@icloud.com"}]
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster, rows, {})
        self.assertFalse(result)
        self.assertEqual(status, "ownership_conflict")

    def test_deux_adresses_pour_meme_compte_sont_ambigues(self):
        rows = self.lines + [dict(self.lines[0], mail="alternative@example.invalid")]
        result, status = unique_aliases("u100", "Sophie", "Diamondra", self.roster, rows, {})
        self.assertFalse(result)
        self.assertEqual(status, "ownership_conflict")


    def test_gerant_prenom_clipping_creatrice(self):
        # 19/10 (Rianah) : créatrice Discord Chloé, comptes « Rianah Clipping Sarah » sur l'onglet Sarah.
        roster = {"r1": {"creatrice": "Chloé", "prenom": "Rianah", "active": True}}
        rows = [
            {"creatrice": "Chloé", "gerant": "Rianah Clipping Chloé", "handle": "c.one", "mail": "c1@icloud.com"},
            {"creatrice": "Sarah", "gerant": "Rianah Clipping Sarah", "handle": "s.one", "mail": "s1@icloud.com"},
            {"creatrice": "Sarah", "gerant": "Rianah Clipping Sarah", "handle": "s.two", "mail": "s2@icloud.com"},
            {"creatrice": "Sarah", "gerant": "Rianah Metricool", "handle": "s.metri", "mail": "m@icloud.com"},
            {"creatrice": "Sarah", "gerant": "Rianah Clipping Chloé", "handle": "s.faux", "mail": "faux@icloud.com"},
        ]
        result, status = unique_aliases("r1", "Chloé", "Rianah", roster, rows, {})
        self.assertEqual(status, "matched")
        self.assertEqual(result, {"c1@icloud.com", "s1@icloud.com", "s2@icloud.com"})


if __name__ == "__main__":
    unittest.main()
