"""18/10 (action 26) : aucun code Instagram reçu depuis 3 h, de jour à Paris → une ligne au salon admin. Cas fictifs."""
import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import codes_2fa as c  # noqa: E402

MAINTENANT = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


class SilenceTests(unittest.TestCase):
    def test_seuil_et_plage_de_jour(self):
        iso = (MAINTENANT - timedelta(minutes=200)).isoformat()
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 14, 180, (9, 23)), 200)
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 3, 180, (9, 23)), 0)       # la nuit : normal
        recent = (MAINTENANT - timedelta(minutes=30)).isoformat()
        self.assertEqual(c.silence_a_signaler(recent, MAINTENANT, 14, 180, (9, 23)), 0)
        self.assertEqual(c.silence_a_signaler(iso, MAINTENANT, 14, 0, (9, 23)), 0)        # coupée

    def test_une_fois_puis_retour(self):
        etat = {"dernier_code": (MAINTENANT - timedelta(hours=4)).isoformat()}
        dits = []

        async def admin(t):
            dits.append(t)
            return True
        with patch.object(c, "_etat", lambda: etat), patch.object(c, "_sauver", lambda: None), \
                patch.object(c, "_admin", admin), patch.object(c, "_maintenant", lambda: MAINTENANT), \
                patch.object(c, "SILENCE_MIN", 180), patch.object(c, "SILENCE_HEURES", (0, 24)):
            asyncio.run(c.surveiller_silence())
            asyncio.run(c.surveiller_silence())                         # pas deux fois
            etat["dernier_code"] = MAINTENANT.isoformat()                # un code arrive
            asyncio.run(c.surveiller_silence())
        self.assertEqual(len(dits), 2)
        self.assertIn("Aucun code Instagram reçu depuis 4 h 00", dits[0])
        self.assertIn("arrivent de nouveau", dits[1])


if __name__ == "__main__":
    unittest.main()
