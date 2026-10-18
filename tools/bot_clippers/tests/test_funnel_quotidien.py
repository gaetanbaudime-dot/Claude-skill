"""18/10 (actions 16-17) : M1 · M2 · M3 jour par jour, définitions gelées. Cas fictifs."""
import sys
import unittest
from datetime import date, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import funnel_quotidien as f  # noqa: E402

J = date(2026, 10, 17)
PIPE = {
    "arrivees": {"1": {"date": "2026-10-17T10:00:00+00:00"},    # quiz la veille : qualifié
                 "2": {"date": "2026-10-17T11:00:00+00:00"},    # quiz 3 jours avant : pas qualifié (pas sous 24 h)
                 "3": {"date": "2026-10-17T12:00:00+00:00"},    # quiz raté
                 "4": {"date": "2026-10-16T12:00:00+00:00"}},   # arrivé un autre jour
    "etats": {"1": {"etat": "valide", "date_quiz": "2026-10-16T20:00:00+00:00"},
              "2": {"etat": "valide", "date_quiz": "2026-10-14T20:00:00+00:00"},
              "3": {"etat": "quiz_rate", "date_quiz": "2026-10-17T09:00:00+00:00"},
              "4": {"etat": "valide", "date_quiz": "2026-10-16T09:00:00+00:00"}}}


class FunnelTests(unittest.TestCase):
    def test_m2_quiz_et_discord_sous_24h(self):
        self.assertEqual(f.qualifies(PIPE, J, timezone.utc), ["1"])

    def test_m3_jour_tenu_a_5(self):
        paie = {"liens": {"a": {"uid": "1"}, "b": {"uid": "2"}, "c": {"uid": "9"}, "d": {"uid": "3", "archive": True}}}
        visites = {"1": 5, "2": 4, "9": 40, "3": 99}
        self.assertEqual(f.actifs(paie, J, lambda d, uid, a, b: visites[uid], exclus={"9"}), ["1"])

    def test_textes(self):
        lignes = f.serie([J, date(2026, 10, 16)], lambda j: 10, lambda j: 3, lambda j: 2)
        self.assertIn("M1 **10** · M2 **3** · M3 **2**", f.texte(lignes))
        self.assertIn("M2/M1 30 %", f.texte(lignes))
        self.assertIn("10 lead(s) · 3 qualifié(s) · 2 actif(s)", f.ligne_digest(lignes))
        self.assertEqual(f.lignes_feuille(lignes)[1][0], "16/10/2026")


if __name__ == "__main__":
    unittest.main()
