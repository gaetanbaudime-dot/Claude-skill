"""18/10 : le TL entre dans un salon dont tous les messages viennent du bot ou du clipper (Georgial). Cas fictifs."""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onboarding_preuves as op  # noqa: E402


def salon(auteurs, lisible=True):
    moi = N(id=1)

    async def history(limit=None):
        for a in auteurs[:limit]:
            yield N(author=N(id=a))
    return N(guild=N(me=moi), permissions_for=lambda m: N(view_channel=lisible, read_message_history=lisible), history=history)


class PartageableTests(unittest.TestCase):
    def test_bot_et_clipper_seulement(self):
        self.assertTrue(asyncio.run(op.salon_partageable(salon([1, 7, 1]), "7")))
        self.assertTrue(asyncio.run(op.salon_partageable(salon([]), "7")))

    def test_tiers_ou_illisible_bloque(self):
        self.assertFalse(asyncio.run(op.salon_partageable(salon([1, 9]), "7")))
        self.assertFalse(asyncio.run(op.salon_partageable(salon([1], lisible=False), "7")))
        self.assertFalse(asyncio.run(op.salon_partageable(salon([1] * 5), "7", limite=3)))


if __name__ == "__main__":
    unittest.main()
